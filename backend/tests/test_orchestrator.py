"""Orchestrator intent classification + synthesis unit tests."""
from __future__ import annotations

from typing import Any

import pytest

from mokn.agents.orchestrator import IntentClassification, OrchestratorAgent


@pytest.mark.asyncio
async def test_classifies_regulation_question(fake_gemini: Any) -> None:
    def responder(prompt: str, schema: type[Any] | None) -> Any:
        assert schema is IntentClassification
        return IntentClassification(
            intent="regulation_question",
            rationale="الطالب يسأل عن حد الساعات.",
        )

    fake_gemini.responder = responder
    orch = OrchestratorAgent(llm=fake_gemini)
    result = await orch.classify_intent("كم الحد الأقصى للساعات لطالب معدله 2.5؟")
    assert result.intent == "regulation_question"


@pytest.mark.asyncio
async def test_classifies_build_schedule_with_hours(fake_gemini: Any) -> None:
    def responder(prompt: str, schema: type[Any] | None) -> Any:
        return IntentClassification(
            intent="build_schedule",
            target_hours=15,
            target_semester="fall-2026",
            rationale="طلب بناء جدول صريح.",
        )

    fake_gemini.responder = responder
    orch = OrchestratorAgent(llm=fake_gemini)
    result = await orch.classify_intent("ابني لي جدول 15 ساعة للفصل القادم")
    assert result.intent == "build_schedule"
    assert result.target_hours == 15
    assert result.target_semester == "fall-2026"


@pytest.mark.asyncio
async def test_classifies_build_schedule_defaults_when_missing(fake_gemini: Any) -> None:
    """If the LLM returns build_schedule but omits hours/semester, Orchestrator
    fills in sensible defaults so downstream nodes never see None."""

    def responder(prompt: str, schema: type[Any] | None) -> Any:
        return IntentClassification(
            intent="build_schedule",
            target_hours=None,
            target_semester=None,
            rationale="بدون تحديد ساعات.",
        )

    fake_gemini.responder = responder
    orch = OrchestratorAgent(
        llm=fake_gemini, default_semester="fall-2026", default_target_hours=15
    )
    result = await orch.classify_intent("ابني لي جدول")
    assert result.target_hours == 15
    assert result.target_semester == "fall-2026"


@pytest.mark.asyncio
async def test_classifies_unknown(fake_gemini: Any) -> None:
    def responder(prompt: str, schema: type[Any] | None) -> Any:
        return IntentClassification(intent="unknown", rationale="غير واضح")

    fake_gemini.responder = responder
    orch = OrchestratorAgent(llm=fake_gemini)
    result = await orch.classify_intent("أبغى شاورما")
    assert result.intent == "unknown"


@pytest.mark.asyncio
async def test_synthesize_regulation_only_returns_text(fake_gemini: Any) -> None:
    """synthesize_final_answer must return a plain string, not a model."""
    from mokn.schemas.regulations import RegulationAnswer

    def responder(prompt: str, schema: type[Any] | None) -> Any:
        assert schema is None  # synthesis uses free-text mode
        return "إجابتك: الحد الأقصى 15 ساعة."

    fake_gemini.responder = responder
    orch = OrchestratorAgent(llm=fake_gemini)
    text = await orch.synthesize_final_answer(
        request="كم الحد الأقصى؟",
        outcome="regulation_only",
        round_number=0,
        legis_answer=RegulationAnswer(
            answer="الحد الأقصى 15 ساعة لطالب معدله 2.8.",
            citations=[],
            confidence="medium",
        ),
    )
    assert "15 ساعة" in text


@pytest.mark.asyncio
async def test_orchestrator_never_vetoes(fake_gemini: Any) -> None:
    orch = OrchestratorAgent(llm=fake_gemini)
    assert await orch.can_veto({"type": "schedule"}) is None
    assert fake_gemini.calls == []
