"""NegotiationStore save/load/list + corrupted-file handling."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from mokn.negotiation.store import NegotiationStore
from mokn.schemas.negotiation import (
    NegotiationOutcome,
    NegotiationSession,
    NegotiationTurn,
    TurnType,
)


def _sample_session(sid: str = "sess-abc123") -> NegotiationSession:
    return NegotiationSession(
        session_id=sid,
        student_id="442001234",
        user_request="ابني لي جدول 12 ساعة",
        intent="build_schedule",
        turns=[
            NegotiationTurn(
                session_id=sid,
                round_number=0,
                turn_type=TurnType.USER_REQUEST,
                agent=None,
                content={"request": "ابني لي جدول"},
                summary="الطالب: ابني لي جدول",
                timestamp=datetime.now(tz=timezone.utc),
            ),
            NegotiationTurn(
                session_id=sid,
                round_number=0,
                turn_type=TurnType.ORCHESTRATOR_CLASSIFY,
                agent="Orchestrator",
                content={"intent": "build_schedule"},
                summary="Orchestrator: تصنيف طلب جدول",
                timestamp=datetime.now(tz=timezone.utc),
            ),
        ],
        outcome=NegotiationOutcome.APPROVED,
        final_answer="جدولك جاهز.",
        final_proposal=None,
    )


@pytest.mark.asyncio
async def test_save_then_get_roundtrips(tmp_path: Path) -> None:
    store = NegotiationStore(tmp_path)
    original = _sample_session("sess-001")
    await store.save(original)
    loaded = await store.get("sess-001")
    assert loaded is not None
    assert loaded.session_id == "sess-001"
    assert loaded.outcome == NegotiationOutcome.APPROVED
    assert loaded.final_answer == "جدولك جاهز."
    assert len(loaded.turns) == 2
    assert loaded.turns[0].turn_type == TurnType.USER_REQUEST


@pytest.mark.asyncio
async def test_get_returns_none_for_missing(tmp_path: Path) -> None:
    store = NegotiationStore(tmp_path)
    assert await store.get("does-not-exist") is None


@pytest.mark.asyncio
async def test_list_recent_is_ordered_by_mtime(tmp_path: Path) -> None:
    import os
    import time

    store = NegotiationStore(tmp_path)
    s1 = _sample_session("older")
    s2 = _sample_session("newer")
    await store.save(s1)
    # Nudge mtimes so ordering is deterministic.
    time.sleep(0.01)
    await store.save(s2)
    older = tmp_path / "older.json"
    newer = tmp_path / "newer.json"
    os.utime(older, (older.stat().st_atime, older.stat().st_mtime - 10))

    listed = await store.list_recent(limit=10)
    assert [s.session_id for s in listed] == ["newer", "older"]


@pytest.mark.asyncio
async def test_list_respects_limit(tmp_path: Path) -> None:
    store = NegotiationStore(tmp_path)
    for i in range(5):
        await store.save(_sample_session(f"s{i}"))
    listed = await store.list_recent(limit=2)
    assert len(listed) == 2


@pytest.mark.asyncio
async def test_corrupted_file_is_skipped(tmp_path: Path) -> None:
    store = NegotiationStore(tmp_path)
    good = _sample_session("good-one")
    await store.save(good)
    (tmp_path / "broken.json").write_text("{ this is not valid json")

    loaded = await store.get("broken")
    assert loaded is None

    listed = await store.list_recent(limit=10)
    assert [s.session_id for s in listed] == ["good-one"]
