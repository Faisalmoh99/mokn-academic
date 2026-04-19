"""End-to-end: a student whose eligible pool can't hit the floor must short-circuit.

Before this fix, Planner returned a fake `empty` schedule, Legis vetoed it
for being below 12 hours, constraint extractor produced nothing new, and
the loop ran all three rounds before escalating with a generic message.

This test wires real PlannerAgent + real graph + a fake Gemini + a fake
Legis and locks in:
  * Outcome is `escalated` in a single Planner round (no pointless retries).
  * The Planner turn carries the `no_solution` flag.
  * The orchestrator's final answer mentions insufficient eligible courses
    (not a generic "we couldn't agree" template).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mokn.agents.orchestrator import IntentClassification
from mokn.agents.planner import PlannerAgent, _PlannerDecision
from mokn.data.repository import CourseRepository, StudentRepository
from mokn.negotiation.constraint_extractor import (
    _ExtractedConstraints,
    extract_constraints_from_objections,
)
from mokn.negotiation.graph import run_negotiation
from mokn.planning.optimizer import HardConstraints
from mokn.schemas.agent import VetoDecision
from mokn.schemas.negotiation import NegotiationOutcome, TurnType
from mokn.schemas.schedule import ScheduleProposal

_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "mock"


@pytest.fixture
def students_repo() -> StudentRepository:
    return StudentRepository(_DATA_DIR / "students.json")


@pytest.fixture
def courses_repo() -> CourseRepository:
    return CourseRepository(_DATA_DIR / "courses.json")


class _FakeOrchestrator:
    def __init__(self, *, target_hours: int, target_semester: str) -> None:
        self._target_hours = target_hours
        self._target_semester = target_semester

    async def classify_intent(self, request: str) -> IntentClassification:
        return IntentClassification(
            intent="build_schedule",
            target_hours=self._target_hours,
            target_semester=self._target_semester,
            rationale="test",
        )

    async def synthesize_final_answer(self, **kwargs: Any) -> str:
        proposal = kwargs.get("proposal")
        outcome = kwargs.get("outcome")
        # Mimic the real orchestrator's no_solution branch behavior: produce
        # a message that mentions insufficient eligible courses. Tests assert
        # on the signal, not on the LLM's phrasing.
        if proposal is not None and getattr(proposal, "no_solution", False):
            return (
                "عذراً، المواد المؤهلة لك في هذا الفصل لا تكفي لبناء جدول بالحد "
                "الأدنى المطلوب. يرجى مراجعة المرشد الأكاديمي."
            )
        return f"[fake outcome={outcome}]"


class _FakeLegis:
    """Records calls but should never be called on the no_solution path."""

    def __init__(self) -> None:
        self.veto_calls: list[dict[str, Any]] = []

    async def can_veto(
        self, proposal: Any, *, context: Any | None = None
    ) -> VetoDecision | None:
        self.veto_calls.append({"proposal": proposal, "context": context})
        return None  # would approve, but we don't expect to reach here


class _DispatchingFakeGemini:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.3,
        response_schema: type | None = None,
        model: str | None = None,
    ) -> Any:
        name = response_schema.__name__ if response_schema else None
        self.calls.append(name or "text")
        if name == "_PlannerDecision":
            # Planner won't actually reach the ranker on no_solution (the
            # agent short-circuits before building options), but stage a
            # default just in case the eligible pool turns out viable.
            return _PlannerDecision(
                recommended_option="balanced",
                warnings=[],
                constraints_considered=[],
                per_option_reasoning={},
            )
        if name == "_ExtractedConstraints":
            return _ExtractedConstraints(rationale="none")
        raise AssertionError(f"unexpected schema in fake gemini: {name}")


@pytest.mark.asyncio
async def test_thin_pool_escalates_in_one_round_with_specific_message(
    students_repo: StudentRepository,
    courses_repo: CourseRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Force a thin eligible pool → expect escalated outcome + no_solution flag."""
    # Monkeypatch the course repo so Planner sees only one course (can't hit 12h).
    from mokn.schemas.course import Course

    real_list_available = courses_repo.list_available

    async def thin_list(completed: Any) -> list[Course]:
        all_courses = await real_list_available(completed)
        return all_courses[:1]  # one course, 3 credits — below the 12-credit floor

    monkeypatch.setattr(courses_repo, "list_available", thin_list)

    fake_llm = _DispatchingFakeGemini()
    orch = _FakeOrchestrator(target_hours=15, target_semester="fall-2026")
    planner = PlannerAgent(students=students_repo, courses=courses_repo, llm=fake_llm)
    legis = _FakeLegis()

    async def extractor(objs: list[str]) -> HardConstraints:
        return await extract_constraints_from_objections(objs, llm=fake_llm)

    session = await run_negotiation(
        user_request="ابني لي جدول 15 ساعة",
        student_id="442001234",
        orchestrator=orch,  # type: ignore[arg-type]
        planner=planner,
        legis=legis,  # type: ignore[arg-type]
        students=students_repo,
        courses=courses_repo,
        constraints_extractor=extractor,
    )

    # Outcome is escalated — not approved, not max_rounds — and Legis was not consulted.
    assert session.outcome == NegotiationOutcome.ESCALATED
    assert legis.veto_calls == [], "Legis must not be invoked when Planner has no solution"

    # Exactly one Planner round; no retries.
    proposal_turns = [t for t in session.turns if t.turn_type == TurnType.PLANNER_PROPOSE]
    assert len(proposal_turns) == 1, (
        f"expected a single Planner round, got {len(proposal_turns)} — no_solution should short-circuit"
    )

    # That turn's proposal carries the no_solution flag and an honest warning.
    content = proposal_turns[0].content
    proposal = ScheduleProposal.model_validate(content)
    assert proposal.no_solution is True
    assert proposal.options == []
    assert any("كافية" in w or "كافٍ" in w for w in proposal.warnings), (
        f"expected Arabic warning mentioning insufficient courses, got: {proposal.warnings}"
    )

    # Final answer mentions the real reason, not a generic "couldn't agree".
    assert session.final_answer is not None
    assert "المواد" in session.final_answer
    assert "اتفاق" not in session.final_answer, (
        "final answer should not read like a generic negotiation-failed template"
    )
