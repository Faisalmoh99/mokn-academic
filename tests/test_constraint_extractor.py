"""Tests for the Legis-objection → HardConstraints distillation step.

These guard the lever that makes round 2 differ from round 1: if this
extractor returns empty, the negotiation degenerates back into the bug
where Planner re-proposes the same schedule.
"""
from __future__ import annotations

from typing import Any

import pytest

from mokn.negotiation.constraint_extractor import (
    _ExtractedConstraints,
    extract_constraints_from_objections,
)
from mokn.planning.optimizer import HardConstraints


@pytest.mark.asyncio
async def test_extracts_min_credits(fake_gemini: Any) -> None:
    def responder(prompt: str, schema: type[Any] | None) -> Any:
        assert schema is _ExtractedConstraints
        assert "الحد الأدنى" in prompt
        return _ExtractedConstraints(min_credits=12, rationale="حد أدنى 12 ساعة.")

    fake_gemini.responder = responder
    result = await extract_constraints_from_objections(
        ["يخالف المادة 14 — الحد الأدنى للساعات 12 ساعة."],
        llm=fake_gemini,
    )
    assert result.min_credits == 12
    assert result.max_credits is None


@pytest.mark.asyncio
async def test_extracts_max_credits(fake_gemini: Any) -> None:
    def responder(prompt: str, schema: type[Any] | None) -> Any:
        return _ExtractedConstraints(max_credits=15, rationale="حد أقصى 15.")

    fake_gemini.responder = responder
    result = await extract_constraints_from_objections(
        ["معدل 2.1 يسمح بحد أقصى 15 ساعة وفق المادة 14."],
        llm=fake_gemini,
    )
    assert result.max_credits == 15
    assert result.min_credits is None


@pytest.mark.asyncio
async def test_extracts_excluded_and_required(fake_gemini: Any) -> None:
    def responder(prompt: str, schema: type[Any] | None) -> Any:
        return _ExtractedConstraints(
            excluded_courses=["CS302"],
            required_courses=["CS101"],
            rationale="استبعاد CS302، إلزام CS101.",
        )

    fake_gemini.responder = responder
    result = await extract_constraints_from_objections(
        ["لم يجتز متطلب CS101 — لا تسجّل CS302 قبله."],
        llm=fake_gemini,
    )
    assert result.excluded_courses == {"CS302"}
    assert result.required_courses == {"CS101"}


@pytest.mark.asyncio
async def test_empty_objections_short_circuits(fake_gemini: Any) -> None:
    """No LLM call when there's nothing to extract — saves a round-trip."""
    result = await extract_constraints_from_objections([], llm=fake_gemini)
    assert isinstance(result, HardConstraints)
    assert result.is_empty()
    assert fake_gemini.calls == []


@pytest.mark.asyncio
async def test_inverted_bounds_returns_empty(fake_gemini: Any) -> None:
    """If the LLM produces min>max, treat it as no extraction rather than
    handing the solver a contradictory window."""

    def responder(prompt: str, schema: type[Any] | None) -> Any:
        return _ExtractedConstraints(min_credits=18, max_credits=12, rationale="bug")

    fake_gemini.responder = responder
    result = await extract_constraints_from_objections(
        ["something"],
        llm=fake_gemini,
    )
    assert result.is_empty()
