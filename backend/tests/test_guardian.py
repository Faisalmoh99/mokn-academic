"""GuardianAgent tests with a mocked Gemini client.

The risk layer is already covered in test_risk_rules.py. Here we focus on
the prose agent: prompt assembly, structured output handling, vetoing
behavior, and graceful fallback.
"""
from __future__ import annotations

from typing import Any

import pytest

from mokn.agents.guardian import (
    GUARDIAN_SYSTEM_PROMPT,
    GuardianAgent,
    _GuardianOutput,
    _GuardianRecommendationDraft,
)
from mokn.schemas.agent import AgentContext
from mokn.schemas.guardian import (
    RiskAssessment,
    RiskFactor,
    RiskSeverity,
)


def _assessment(severity: RiskSeverity = RiskSeverity.HIGH) -> RiskAssessment:
    return RiskAssessment(
        student_id="442009876",
        student_name="سعود ناصر الدوسري",
        overall_severity=severity,
        factors=[
            RiskFactor(
                factor_type="attendance_high",
                course_code="CS201",
                description_ar="غياب 5/6 في CS201",
                severity=RiskSeverity.HIGH,
                evidence={"absences": 5, "limit": 6},
            )
        ],
        summary_ar="مستوى المخاطرة مرتفع.",
    )


def _staged_output() -> _GuardianOutput:
    return _GuardianOutput(
        message_ar="مرحباً سعود، نلاحظ غياباً مرتفعاً في CS201. يُفضل مراجعة المرشد.",
        recommendations=[
            _GuardianRecommendationDraft(
                title_ar="تحسين الحضور",
                rationale_ar="نسبة الغياب الحالية تقترب من حد الحرمان.",
                suggested_action="improve_attendance",
                priority="urgent",
            )
        ],
    )


@pytest.mark.asyncio
async def test_guardian_process_returns_structured_response(fake_gemini: Any) -> None:
    def responder(prompt: str, schema: type[Any] | None) -> Any:
        assert schema is _GuardianOutput
        # The pre-computed assessment must reach the prompt verbatim.
        assert "CS201" in prompt
        assert "سعود" in prompt
        return _staged_output()

    fake_gemini.responder = responder
    agent = GuardianAgent(llm=fake_gemini)
    response = await agent.process(
        AgentContext(
            query="فحص استباقي",
            student_id="442009876",
            metadata={"assessment": _assessment()},
        )
    )

    assert response.agent == "Guardian"
    assert "سعود" in response.content["message_ar"]
    assert response.content["assessment"]["student_id"] == "442009876"
    assert len(response.content["recommendations"]) == 1
    assert response.content["recommendations"][0]["suggested_action"] == "improve_attendance"
    assert response.confidence in {"high", "medium", "low"}


@pytest.mark.asyncio
async def test_guardian_process_accepts_dict_assessment(fake_gemini: Any) -> None:
    fake_gemini.responder = lambda prompt, schema: _staged_output()
    agent = GuardianAgent(llm=fake_gemini)
    response = await agent.process(
        AgentContext(
            query="x",
            metadata={"assessment": _assessment().model_dump()},
        )
    )
    assert response.agent == "Guardian"


@pytest.mark.asyncio
async def test_guardian_process_raises_when_assessment_missing(fake_gemini: Any) -> None:
    agent = GuardianAgent(llm=fake_gemini)
    with pytest.raises(ValueError, match="assessment"):
        await agent.process(AgentContext(query="x"))
    # No LLM call should be made before the precondition check fails.
    assert fake_gemini.calls == []


@pytest.mark.asyncio
async def test_guardian_can_veto_always_none() -> None:
    """Guardian is a suggester, not a gatekeeper. This is contractual."""
    agent = GuardianAgent(llm=None)  # llm not used by can_veto
    assert (
        await agent.can_veto(
            {
                "type": "schedule",
                "courses": [{"code": "CS201", "credits": 3}],
                "total_credits": 18,
            }
        )
        is None
    )
    # Also abstains on regulation-shaped or random proposals.
    assert await agent.can_veto({"type": "anything"}) is None


@pytest.mark.asyncio
async def test_guardian_system_prompt_includes_critical_phrases() -> None:
    """If anyone weakens the prompt's hard constraints, this trips."""
    assert GUARDIAN_SYSTEM_PROMPT
    assert "Guardian" in GUARDIAN_SYSTEM_PROMPT
    assert "اقترح" in GUARDIAN_SYSTEM_PROMPT
    # The "no veto" intent is encoded as "لا تفرض" — guard it.
    assert "لا تفرض" in GUARDIAN_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_guardian_falls_back_when_llm_raises(fake_gemini: Any) -> None:
    def responder(prompt: str, schema: type[Any] | None) -> Any:
        raise RuntimeError("simulated Gemini outage")

    fake_gemini.responder = responder
    agent = GuardianAgent(llm=fake_gemini)
    response = await agent.process(
        AgentContext(
            query="x",
            metadata={"assessment": _assessment()},
        )
    )
    # Fallback message must still mention the student by first name.
    assert "سعود" in response.content["message_ar"]
    assert response.content["recommendations"], "fallback should still suggest something"


@pytest.mark.asyncio
async def test_guardian_low_severity_path_works(fake_gemini: Any) -> None:
    fake_gemini.responder = lambda prompt, schema: _staged_output()
    agent = GuardianAgent(llm=fake_gemini)
    response = await agent.process(
        AgentContext(
            query="x",
            metadata={"assessment": _assessment(RiskSeverity.LOW)},
        )
    )
    assert response.confidence == "low"
