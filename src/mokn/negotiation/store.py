"""JSON-file persistence for completed negotiation sessions.

The dashboard (Session 5) will replay these for the demo; Firestore will
eventually replace the filesystem but the interface stays the same. We write
one file per session — cheap, human-readable, and doesn't need an index.
"""
from __future__ import annotations

import asyncio
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from mokn.schemas.negotiation import NegotiationSession

logger = logging.getLogger(__name__)

_DEFAULT_SESSIONS_DIR = Path(__file__).resolve().parents[3] / "data" / "sessions"


class NegotiationStore:
    """Filesystem-backed store. One JSON file per session."""

    def __init__(self, storage_dir: Path | str) -> None:
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, session_id: str) -> Path:
        safe = session_id.replace("/", "_")
        return self._dir / f"{safe}.json"

    async def save(self, session: NegotiationSession) -> None:
        payload = session.model_dump_json(indent=2)
        path = self._path_for(session.session_id)
        await asyncio.to_thread(path.write_text, payload, "utf-8")

    async def get(self, session_id: str) -> NegotiationSession | None:
        path = self._path_for(session_id)
        if not path.exists():
            return None

        def _read() -> NegotiationSession | None:
            try:
                return NegotiationSession.model_validate_json(path.read_text("utf-8"))
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning("corrupted session file %s: %s", path, exc)
                return None

        return await asyncio.to_thread(_read)

    async def list_recent(self, limit: int = 20) -> list[NegotiationSession]:
        paths = sorted(
            self._dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:limit]
        sessions = await asyncio.gather(
            *(self._load_quiet(p) for p in paths)
        )
        return [s for s in sessions if s is not None]

    async def _load_quiet(self, path: Path) -> NegotiationSession | None:
        def _read() -> NegotiationSession | None:
            try:
                return NegotiationSession.model_validate_json(path.read_text("utf-8"))
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning("skipping corrupted session file %s: %s", path, exc)
                return None

        return await asyncio.to_thread(_read)

    def list_ids(self) -> Iterable[str]:
        """Sync helper used by tests and maintenance scripts."""
        return (p.stem for p in self._dir.glob("*.json"))


@lru_cache(maxsize=1)
def get_default_store() -> NegotiationStore:
    return NegotiationStore(_DEFAULT_SESSIONS_DIR)
