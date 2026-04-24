"""Shared test fixtures.

Strategy:
- Force settings to a tmp chroma dir and a fake Gemini key before Settings loads.
- Replace the SentenceTransformer embedding function with a deterministic
  token-hash fake: no model download, deterministic in-memory behaviour,
  sub-second tests.
- Provide a FakeGeminiClient that returns whatever the test stages.
"""
from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

# Settings must see valid env before `get_settings()` is cached by any import.
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-used")
os.environ.setdefault("ENV", "test")

from mokn.config import get_settings  # noqa: E402
from mokn.memory.knowledge import KnowledgeBase  # noqa: E402
from mokn.schemas.regulations import RegulationAnswer  # noqa: E402


_EMBED_DIM = 64


class DeterministicHashEmbedding:
    """Fake embedding function: hashes tokens into a fixed-dim float vector.

    Satisfies both the old Chroma protocol (`__call__`) and the new one
    (`embed_documents` + `embed_query`). Chroma still does real nearest-
    neighbor search, so semantically similar texts that share tokens
    retrieve well enough for our tests.
    """

    def __init__(self, dim: int = _EMBED_DIM) -> None:
        self._dim = dim

    def __call__(self, input: list[str]) -> list[list[float]]:  # noqa: A002 (Chroma API)
        return [self._embed(text) for text in input]

    def embed_documents(self, input: list[str]) -> list[list[float]]:  # noqa: A002
        return [self._embed(text) for text in input]

    def embed_query(self, input: str | list[str]) -> list[list[float]]:  # noqa: A002
        if isinstance(input, str):
            return [self._embed(input)]
        return [self._embed(t) for t in input]

    def name(self) -> str:
        return "deterministic-hash"

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        tokens = text.split()
        if not tokens:
            return vec
        for tok in tokens:
            h = hashlib.sha256(tok.encode("utf-8")).digest()
            for i in range(self._dim):
                vec[i] += (h[i % len(h)] - 128) / 128.0
        norm = sum(v * v for v in vec) ** 0.5 or 1.0
        return [v / norm for v in vec]


@pytest.fixture
def tmp_chroma_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "chroma"
    d.mkdir()
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(d))
    get_settings.cache_clear()
    return d


@pytest.fixture
def knowledge_base(tmp_chroma_dir: Path) -> KnowledgeBase:
    return KnowledgeBase(
        collection_name="regulations_test",
        persist_dir=str(tmp_chroma_dir),
        embedding_model="test-fake",
        embedding_fn=DeterministicHashEmbedding(),
    )


@pytest.fixture
async def seeded_kb(knowledge_base: KnowledgeBase, tmp_path: Path) -> KnowledgeBase:
    """KB pre-loaded with a few Arabic passages covering our test topics."""
    docs = {
        "credit.txt": (
            "المادة 14: العبء الدراسي الطالب يُسمح له بتسجيل 18 ساعة فقط عند "
            "معدل تراكمي 3.0 أو أعلى. الطالب بمعدل بين 2.0 و 2.99 حده الأقصى "
            "15 ساعة معتمدة. أقل من 2.0 حده 12 ساعة."
        ),
        "prereq.txt": (
            "المادة 22: المتطلبات السابقة لا يجوز تسجيل مادة قبل اجتياز متطلبها "
            "السابق. برمجة 2 يشترط لها برمجة 1 بتقدير مقبول على الأقل."
        ),
        "attendance.txt": (
            "المادة 31: الحرمان بسبب الغياب إذا تجاوز غياب الطالب 25% من المحاضرات "
            "فإنه يُحرم من الاختبار النهائي. إنذار كتابي عند 15% و 20%."
        ),
    }
    for name, text in docs.items():
        p = tmp_path / name
        p.write_text(text, encoding="utf-8")
        await knowledge_base.ingest_document(str(p))
    return knowledge_base


class FakeGeminiClient:
    """Hand-staged Gemini replacement. Set `.responder` per test."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.responder: Callable[[str, type | None], Any] | None = None

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.3,
        response_schema: type | None = None,
        model: str | None = None,
    ) -> Any:
        self.calls.append(
            {
                "prompt": prompt,
                "system": system,
                "temperature": temperature,
                "schema": response_schema.__name__ if response_schema else None,
            }
        )
        if self.responder is None:
            raise AssertionError("FakeGeminiClient.responder not set for this test")
        return self.responder(prompt, response_schema)


@pytest.fixture
def fake_gemini() -> Iterator[FakeGeminiClient]:
    yield FakeGeminiClient()


@pytest.fixture
def default_answer() -> RegulationAnswer:
    return RegulationAnswer(
        answer="الحد الأقصى للطالب بمعدل 2.8 هو 15 ساعة معتمدة.",
        citations=[],
        confidence="medium",
    )
