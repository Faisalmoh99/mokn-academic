"""KnowledgeBase ingestion + query tests.

Uses a deterministic fake embedding function (see conftest) so tests stay
offline and complete in under a second.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mokn.memory.knowledge import KnowledgeBase


@pytest.mark.asyncio
async def test_ingests_text_file_and_counts_chunks(
    knowledge_base: KnowledgeBase, tmp_path: Path
) -> None:
    sample = tmp_path / "reg.txt"
    sample.write_text(
        "المادة 14: العبء الدراسي "
        "الطالب بمعدل أعلى من 3.0 يسجل 18 ساعة. "
        "الطالب بمعدل بين 2.0 و 2.99 يسجل 15 ساعة كحد أقصى.",
        encoding="utf-8",
    )

    count = await knowledge_base.ingest_document(str(sample))
    assert count >= 1
    assert knowledge_base.count() == count


@pytest.mark.asyncio
async def test_query_returns_relevant_arabic_chunks(
    seeded_kb: KnowledgeBase,
) -> None:
    results = await seeded_kb.query("كم الحد الأقصى للساعات لطالب معدله 2.8؟", top_k=3)
    assert results, "query returned no chunks"
    joined = " ".join(r.text for r in results)
    assert "ساعة" in joined
    # Must preserve source + page metadata
    assert all(r.source for r in results)
    assert all(r.page >= 1 for r in results)


@pytest.mark.asyncio
async def test_missing_file_raises(knowledge_base: KnowledgeBase) -> None:
    with pytest.raises(FileNotFoundError):
        await knowledge_base.ingest_document("/does/not/exist.pdf")
