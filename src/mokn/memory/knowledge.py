"""ChromaDB-backed knowledge base for Legis (and future knowledge agents).

Responsibilities:
- Ingest PDFs into a named collection (500-token chunks, 50-token overlap).
- Preserve source page + section heading in per-chunk metadata.
- Serve top-k semantic queries, returning typed RetrievedChunk instances.

Chroma's SDK is sync; we expose async methods by offloading to threads so
agents can `await` freely.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils import embedding_functions

from mokn.config import Settings, get_settings
from mokn.schemas.regulations import RetrievedChunk

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_TOKENS = 500
DEFAULT_CHUNK_OVERLAP_TOKENS = 50

_SECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^\s*المادة\s*\(?\s*\d+\s*\)?.*$", re.MULTILINE),
    re.compile(r"^\s*الفصل\s+\S+.*$", re.MULTILINE),
    re.compile(r"^\s*الباب\s+\S+.*$", re.MULTILINE),
    re.compile(r"^\s*\d+(?:\.\d+){0,3}\s+\S.{0,80}$", re.MULTILINE),
)


@dataclass(frozen=True)
class _Chunk:
    text: str
    page: int
    section: str | None


class KnowledgeBase:
    """Chroma collection with a multilingual embedding model attached."""

    def __init__(
        self,
        collection_name: str,
        persist_dir: str,
        embedding_model: str,
        *,
        embedding_fn: Any | None = None,
    ) -> None:
        self.collection_name = collection_name
        self.persist_dir = Path(persist_dir).expanduser().resolve()
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.embedding_model_name = embedding_model

        self._client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._embed_fn = (
            embedding_fn
            if embedding_fn is not None
            else embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=embedding_model
            )
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=self._embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

    async def ingest_document(
        self,
        source_path: str,
        metadata: dict[str, Any] | None = None,
        chunk_tokens: int = DEFAULT_CHUNK_TOKENS,
        overlap_tokens: int = DEFAULT_CHUNK_OVERLAP_TOKENS,
    ) -> int:
        """Chunk the file and upsert to Chroma. Returns the chunk count.

        Supports .pdf (via pypdf) and .txt. PDFs carry page numbers naturally;
        text files are treated as a single page.
        """
        path = Path(source_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(source_path)

        pages = await asyncio.to_thread(_read_pages, path)
        chunks = _chunk_pages(
            pages,
            tokens_per_chunk=chunk_tokens,
            overlap_tokens=overlap_tokens,
        )
        if not chunks:
            logger.warning("No content extracted from %s", source_path)
            return 0

        base_meta: dict[str, Any] = {"source": path.name, **(metadata or {})}
        ids = [_chunk_id(path.name, i, c.text) for i, c in enumerate(chunks)]
        docs = [c.text for c in chunks]
        metas = [
            {
                **base_meta,
                "page": c.page,
                "section": c.section or "",
            }
            for c in chunks
        ]

        await asyncio.to_thread(
            self._collection.upsert,
            ids=ids,
            documents=docs,
            metadatas=metas,
        )
        return len(chunks)

    async def query(
        self,
        question: str,
        top_k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        raw = await asyncio.to_thread(
            self._collection.query,
            query_texts=[question],
            n_results=top_k,
            where=filter,
        )
        return _rows_to_chunks(raw)

    def count(self) -> int:
        return self._collection.count()

    def reset(self) -> None:
        """Destroy and recreate the collection — only for scripts/tests."""
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self._embed_fn,
            metadata={"hnsw:space": "cosine"},
        )


def _read_pages(path: Path) -> list[tuple[int, str]]:
    """Return [(page_number, text), ...]. 1-indexed pages."""
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        out: list[tuple[int, str]] = []
        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                out.append((i, text))
        return out

    text = path.read_text(encoding="utf-8")
    return [(1, text)] if text.strip() else []


def _chunk_pages(
    pages: list[tuple[int, str]],
    tokens_per_chunk: int,
    overlap_tokens: int,
) -> list[_Chunk]:
    """Split each page into ~token-sized chunks with overlap.

    Token count is approximated by whitespace-separated words — good enough
    for chunking heuristics. Arabic words count as tokens here; exact BPE
    counts would need the embedding model's tokenizer and aren't worth the
    cost for chunking decisions.
    """
    chunks: list[_Chunk] = []
    for page_no, text in pages:
        sections = _extract_sections(text)
        words = text.split()
        if not words:
            continue
        step = max(1, tokens_per_chunk - overlap_tokens)
        for start in range(0, len(words), step):
            window = words[start : start + tokens_per_chunk]
            if not window:
                break
            chunk_text = " ".join(window)
            section = _nearest_section(text, chunk_text, sections)
            chunks.append(_Chunk(text=chunk_text, page=page_no, section=section))
            if start + tokens_per_chunk >= len(words):
                break
    return chunks


def _extract_sections(text: str) -> list[tuple[int, str]]:
    """Find heading candidates as (offset_in_text, heading_text)."""
    out: list[tuple[int, str]] = []
    for pat in _SECTION_PATTERNS:
        for m in pat.finditer(text):
            heading = m.group().strip()
            if heading:
                out.append((m.start(), heading[:120]))
    out.sort(key=lambda p: p[0])
    return out


def _nearest_section(
    full_text: str, chunk_text: str, sections: list[tuple[int, str]]
) -> str | None:
    """Return the section heading preceding this chunk in the source page."""
    if not sections:
        return None
    idx = full_text.find(chunk_text[:60])
    if idx < 0:
        return sections[0][1]
    preceding = [h for off, h in sections if off <= idx]
    return preceding[-1] if preceding else None


def _chunk_id(source: str, index: int, text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return f"{source}:{index:04d}:{digest}"


def _rows_to_chunks(raw: dict[str, Any]) -> list[RetrievedChunk]:
    ids = (raw.get("ids") or [[]])[0]
    docs = (raw.get("documents") or [[]])[0]
    metas = (raw.get("metadatas") or [[]])[0]
    distances = (raw.get("distances") or [[]])[0]

    out: list[RetrievedChunk] = []
    for chunk_id, doc, meta, dist in zip(ids, docs, metas, distances, strict=False):
        meta = meta or {}
        section = meta.get("section") or None
        out.append(
            RetrievedChunk(
                text=doc,
                source=str(meta.get("source", "unknown")),
                page=int(meta.get("page", 0) or 0),
                section=section if section else None,
                score=float(dist),
                chunk_id=chunk_id,
            )
        )
    return out


@lru_cache(maxsize=8)
def get_knowledge_base(
    collection_name: str = "regulations",
    settings: Settings | None = None,
) -> KnowledgeBase:
    s = settings or get_settings()
    return KnowledgeBase(
        collection_name=collection_name,
        persist_dir=s.chroma_persist_dir,
        embedding_model=s.embedding_model,
    )
