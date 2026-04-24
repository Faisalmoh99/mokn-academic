"""Round-2-must-differ regression: the headline hotfix scenario.

Wires the REAL PlannerAgent + REAL optimizer into the graph (with a fake
Gemini backing both the Planner ranker and the constraint extractor, and a
hand-staged Legis). Asserts that after a max-credits veto in round 1, the
Planner's round-2 proposal has fewer credits — proof that the negotiation
loop is no longer cosmetic.
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
from mokn.schemas.agent import AgentResponse, VetoDecision
from mokn.schemas.negotiation import NegotiationOutcome, TurnType
from mokn.schemas.regulations import RegulationAnswer
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
        return f"[FAKE outcome={kwargs.get('outcome')}]"


class _FakeLegis:
    """Stages per-call vetoes. Records inputs."""

    def __init__(self, veto_sequence: list[VetoDecision | None]) -> None:
        self._veto_sequence = list(veto_sequence)
        self.veto_calls: list[dict[str, Any]] = []

    async def can_veto(
        self, proposal: Any, *, context: Any | None = None
    ) -> VetoDecision | None:
        self.veto_calls.append({"proposal": proposal, "context": context})
        if not self._veto_sequence:
            return None
        return self._veto_sequence.pop(0)


class _DispatchingFakeGemini:
    """Routes generate() to the right responder by response schema name.

    We need this because the same client is used for two different things in
    the loop: PlannerAgent's _PlannerDecision ranking and the constraint
    extractor's _ExtractedConstraints distillation.
    """

    def __init__(self, *, extracted_max_credits: int | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._max_credits = extracted_max_credits

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
        self.calls.append({"schema": name, "prompt_len": len(prompt)})
        if name == "_PlannerDecision":
            return _PlannerDecision(
                recommended_option="balanced",
                warnings=[],
                constraints_considered=[],
                per_option_reasoning={},
            )
        if name == "_ExtractedConstraints":
            return _ExtractedConstraints(
                max_credits=self._max_credits,
                rationale="حد أقصى من اعتراض Legis.",
            )
        raise AssertionError(f"unexpected schema in fake gemini: {name}")


@pytest.mark.asyncio
async def test_round2_proposal_differs_when_legis_caps_credits(
    students_repo: StudentRepository, courses_repo: CourseRepository
) -> None:
    """Replay of the bug from the hotfix brief.

    Student 442007890 (GPA 2.5, 6 eligible courses = 18 credits) asks for
    18 hours. Legis vetoes round 1 citing a 15-hour cap. Round 2 must
    propose ≤15 credits AND fewer than round 1 — the original bug was that
    Planner re-proposed the identical 18-credit schedule.
    """
    fake_llm = _DispatchingFakeGemini(extracted_max_credits=12)
    orch = _FakeOrchestrator(target_hours=18, target_semester="fall-2026")
    planner = PlannerAgent(
        students=students_repo, courses=courses_repo, llm=fake_llm
    )
    legis = _FakeLegis(
        veto_sequence=[
            VetoDecision(
                agent="Legis",
                veto=True,
                reason="معدل 2.5 — الحد الأقصى 12 ساعة في حالة المراقبة الأكاديمية.",
                violated_rules=["credit-hour-cap"],
                suggestion="خفّض إلى 12 ساعة.",
            ),
            None,  # round 2 approves
        ]
    )

    async def extractor(objs: list[str]) -> HardConstraints:
        return await extract_constraints_from_objections(objs, llm=fake_llm)

    session = await run_negotiation(
        user_request="ابني لي جدول 18 ساعة",
        student_id="442007890",
        orchestrator=orch,  # type: ignore[arg-type]
        planner=planner,
        legis=legis,  # type: ignore[arg-type]
        students=students_repo,
        courses=courses_repo,
        constraints_extractor=extractor,
    )

    assert session.outcome == NegotiationOutcome.APPROVED

    proposal_turns = [t for t in session.turns if t.turn_type == TurnType.PLANNER_PROPOSE]
    assert len(proposal_turns) == 2, "expected exactly two Planner rounds"

    def _recommended_credits(turn_content: dict[str, Any]) -> int:
        proposal = ScheduleProposal.model_validate(turn_content)
        rec_label = proposal.recommended_option
        rec = next(o for o in proposal.options if o.label == rec_label)
        return rec.total_credits

    r1_credits = _recommended_credits(proposal_turns[0].content)
    r2_credits = _recommended_credits(proposal_turns[1].content)

    # Non-negotiable #1: round 2 must obey the regulator's cap (12 here).
    assert r2_credits <= 12, f"round 2 violates the 12-credit cap: {r2_credits}"
    # Non-negotiable #2: round 2 must actually drop below round 1. The
    # original bug had them identical because the solver ignored objections.
    assert r2_credits < r1_credits, (
        f"round 2 credits ({r2_credits}) did not drop below round 1 ({r1_credits}); "
        "Planner ignored Legis's objection"
    )
