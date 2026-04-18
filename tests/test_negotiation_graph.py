"""End-to-end negotiation graph tests with fully faked agents.

No real Gemini, no real KB. We hand-roll minimal agents that implement just
the async methods nodes.py calls — the point of these tests is to verify
graph *flow* (which nodes fire, how many rounds, how legis_objections
accumulate), not agent behavior.

Scenarios covered:
  1. Pure regulation question → legis_only path → outcome=regulation_only
  2. Schedule approved on first try → outcome=approved, round_number=1
  3. Schedule vetoed once then approved → outcome=approved, round_number=2
  4. Persistent veto → outcome=escalated, round_number=max_rounds
  5. Semester-awareness: Legis.can_veto receives a VetoContext whose
     target_semester matches the classifier's choice — not summer.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pytest

from mokn.agents.orchestrator import IntentClassification
from mokn.data.repository import CourseRepository, StudentRepository
from mokn.negotiation.graph import run_negotiation
from mokn.schemas.agent import AgentResponse, VetoDecision
from mokn.schemas.negotiation import NegotiationOutcome, TurnType
from mokn.schemas.regulations import RegulationAnswer
from mokn.schemas.schedule import ScheduleCourse, ScheduleOption, ScheduleProposal

_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "mock"


@pytest.fixture
def students_repo() -> StudentRepository:
    return StudentRepository(_DATA_DIR / "students.json")


@pytest.fixture
def courses_repo() -> CourseRepository:
    return CourseRepository(_DATA_DIR / "courses.json")


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _FakeOrchestrator:
    """Stands in for OrchestratorAgent. Tests stage `classify_responder`."""

    def __init__(
        self,
        *,
        intent: str,
        target_hours: int | None = None,
        target_semester: str | None = None,
    ) -> None:
        self._intent = intent
        self._target_hours = target_hours
        self._target_semester = target_semester
        self.synthesis_calls: list[dict[str, Any]] = []

    async def classify_intent(self, request: str) -> IntentClassification:
        return IntentClassification(
            intent=self._intent,  # type: ignore[arg-type]
            target_hours=self._target_hours,
            target_semester=self._target_semester,
            rationale="test-fixture",
        )

    async def synthesize_final_answer(self, **kwargs: Any) -> str:
        self.synthesis_calls.append(kwargs)
        outcome = kwargs.get("outcome")
        return f"[FAKE_SYNTH outcome={outcome}] الرد النهائي."


class _FakePlanner:
    """Returns a fixed ScheduleProposal. Records every process() call."""

    def __init__(self, proposal_factory: Callable[[int], ScheduleProposal]) -> None:
        self._factory = proposal_factory
        self.calls: list[dict[str, Any]] = []

    async def process(self, context: Any) -> AgentResponse:
        self.calls.append(
            {
                "student_id": context.student_id,
                "metadata": dict(context.metadata),
            }
        )
        round_number = len(self.calls)
        proposal = self._factory(round_number)
        return AgentResponse(
            agent="Planner",
            content=proposal.model_dump(),
            reasoning=f"fake round {round_number}",
            confidence="medium",
        )


class _FakeLegis:
    """Lets the test stage per-call veto decisions + answer payloads."""

    def __init__(
        self,
        *,
        process_response: RegulationAnswer | None = None,
        veto_sequence: list[VetoDecision | None] | None = None,
    ) -> None:
        self._process_response = process_response
        self._veto_sequence = list(veto_sequence or [])
        self.process_calls: list[Any] = []
        self.veto_calls: list[dict[str, Any]] = []

    async def process(self, context: Any) -> AgentResponse:
        self.process_calls.append(context)
        assert self._process_response is not None, "Legis.process not expected here"
        return AgentResponse(
            agent="Legis",
            content=self._process_response.model_dump(),
            reasoning="fake",
            confidence=self._process_response.confidence,
        )

    async def can_veto(
        self, proposal: Any, *, context: Any | None = None
    ) -> VetoDecision | None:
        self.veto_calls.append({"proposal": proposal, "context": context})
        if not self._veto_sequence:
            return None
        return self._veto_sequence.pop(0)


# ---------------------------------------------------------------------------
# ScheduleProposal factories
# ---------------------------------------------------------------------------
def _mk_course(code: str, credits: int = 3) -> ScheduleCourse:
    return ScheduleCourse(
        course_code=code,
        course_name=f"مادة {code}",
        section_id="101",
        credits=credits,
        days=["sunday", "tuesday"],
        start_time="08:00",
        end_time="09:30",
        instructor="د. فلان",
    )


def _proposal_for_round(round_number: int, *, student_id: str, semester: str) -> ScheduleProposal:
    """Fewer courses each round — mirrors the node's hour step-down."""
    all_codes = ["CS302", "CS310", "CS303", "MATH202", "STAT201", "CS401"]
    picked = all_codes[: max(5 - (round_number - 1), 3)]
    courses = [_mk_course(c) for c in picked]
    total = sum(c.credits for c in courses)
    opt = ScheduleOption(
        label="balanced",
        courses=courses,
        total_credits=total,
        estimated_difficulty=float(total) / 5,
        reasoning="خيار متوازن.",
    )
    return ScheduleProposal(
        student_id=student_id,
        target_semester=semester,
        options=[opt],
        recommended_option="balanced",
        warnings=[],
        constraints_considered=["المتطلبات السابقة"],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_regulation_question_path_only_fires_legis_once(
    students_repo: StudentRepository,
    courses_repo: CourseRepository,
) -> None:
    orch = _FakeOrchestrator(intent="regulation_question")
    planner = _FakePlanner(lambda n: _proposal_for_round(n, student_id="x", semester="fall-2026"))
    legis = _FakeLegis(
        process_response=RegulationAnswer(
            answer="الحد الأقصى 15 ساعة لطالب معدله بين 2.0 و 2.99.",
            citations=[],
            confidence="medium",
        )
    )
    session = await run_negotiation(
        user_request="كم الحد الأقصى للساعات لطالب معدله 2.5؟",
        student_id=None,
        orchestrator=orch,  # type: ignore[arg-type]
        planner=planner,  # type: ignore[arg-type]
        legis=legis,  # type: ignore[arg-type]
        students=students_repo,
        courses=courses_repo,
    )

    assert session.intent == "regulation_question"
    assert session.outcome == NegotiationOutcome.REGULATION_ONLY
    assert session.final_answer is not None
    # Legis.process ran; Legis.can_veto and Planner.process did not.
    assert len(legis.process_calls) == 1
    assert legis.veto_calls == []
    assert planner.calls == []

    turn_types = [t.turn_type for t in session.turns]
    assert TurnType.USER_REQUEST in turn_types
    assert TurnType.ORCHESTRATOR_CLASSIFY in turn_types
    assert TurnType.LEGIS_REVIEW in turn_types
    assert TurnType.ORCHESTRATOR_SYNTHESIZE in turn_types


@pytest.mark.asyncio
async def test_schedule_approved_first_round(
    students_repo: StudentRepository,
    courses_repo: CourseRepository,
) -> None:
    orch = _FakeOrchestrator(
        intent="build_schedule", target_hours=12, target_semester="fall-2026"
    )
    planner = _FakePlanner(
        lambda n: _proposal_for_round(n, student_id="442001234", semester="fall-2026")
    )
    legis = _FakeLegis(veto_sequence=[None])  # no veto → approve

    session = await run_negotiation(
        user_request="ابني لي جدول 12 ساعة للفصل القادم",
        student_id="442001234",
        orchestrator=orch,  # type: ignore[arg-type]
        planner=planner,  # type: ignore[arg-type]
        legis=legis,  # type: ignore[arg-type]
        students=students_repo,
        courses=courses_repo,
    )

    assert session.intent == "build_schedule"
    assert session.outcome == NegotiationOutcome.APPROVED
    assert session.final_proposal is not None
    assert len(planner.calls) == 1
    assert len(legis.veto_calls) == 1

    turn_types = [t.turn_type for t in session.turns]
    assert TurnType.PLANNER_PROPOSE in turn_types
    assert TurnType.LEGIS_APPROVE in turn_types
    # no LEGIS_VETO on the happy path
    assert TurnType.LEGIS_VETO not in turn_types

    # Round numbers recorded on the turns.
    planner_turns = [t for t in session.turns if t.turn_type == TurnType.PLANNER_PROPOSE]
    assert [t.round_number for t in planner_turns] == [1]


@pytest.mark.asyncio
async def test_schedule_veto_then_approve(
    students_repo: StudentRepository,
    courses_repo: CourseRepository,
) -> None:
    orch = _FakeOrchestrator(
        intent="build_schedule", target_hours=18, target_semester="fall-2026"
    )
    planner = _FakePlanner(
        lambda n: _proposal_for_round(n, student_id="442009876", semester="fall-2026")
    )
    legis = _FakeLegis(
        veto_sequence=[
            VetoDecision(
                agent="Legis",
                veto=True,
                reason="معدل 2.8 يسمح بحد أقصى 15 ساعة بحسب المادة 14.",
                violated_rules=["credit-hour-cap"],
                suggestion="خفّض العبء إلى 15 ساعة.",
            ),
            None,  # round 2 approves
        ]
    )

    session = await run_negotiation(
        user_request="ابني لي جدول 18 ساعة",
        student_id="442009876",
        orchestrator=orch,  # type: ignore[arg-type]
        planner=planner,  # type: ignore[arg-type]
        legis=legis,  # type: ignore[arg-type]
        students=students_repo,
        courses=courses_repo,
    )

    assert session.outcome == NegotiationOutcome.APPROVED
    assert len(planner.calls) == 2
    # Second planner call must include prior objection.
    assert planner.calls[1]["metadata"]["prior_objections"], (
        "Planner round 2 must receive prior objections so it can adjust."
    )
    assert len(legis.veto_calls) == 2

    turn_types = [t.turn_type for t in session.turns]
    assert TurnType.LEGIS_VETO in turn_types
    assert TurnType.LEGIS_APPROVE in turn_types

    # Second planner propose must be on round 2.
    planner_turns = [t for t in session.turns if t.turn_type == TurnType.PLANNER_PROPOSE]
    assert [t.round_number for t in planner_turns] == [1, 2]


@pytest.mark.asyncio
async def test_persistent_veto_escalates_at_max_rounds(
    students_repo: StudentRepository,
    courses_repo: CourseRepository,
) -> None:
    orch = _FakeOrchestrator(
        intent="build_schedule", target_hours=18, target_semester="fall-2026"
    )
    planner = _FakePlanner(
        lambda n: _proposal_for_round(n, student_id="442009876", semester="fall-2026")
    )

    def _veto(i: int) -> VetoDecision:
        return VetoDecision(
            agent="Legis",
            veto=True,
            reason=f"اعتراض رقم {i}: مخالفة المادة 14.",
            violated_rules=["credit-hour-cap"],
        )

    legis = _FakeLegis(veto_sequence=[_veto(1), _veto(2), _veto(3)])

    session = await run_negotiation(
        user_request="ابني لي جدول 18 ساعة",
        student_id="442009876",
        orchestrator=orch,  # type: ignore[arg-type]
        planner=planner,  # type: ignore[arg-type]
        legis=legis,  # type: ignore[arg-type]
        students=students_repo,
        courses=courses_repo,
        max_rounds=3,
    )

    assert session.outcome == NegotiationOutcome.ESCALATED
    assert len(planner.calls) == 3
    assert len(legis.veto_calls) == 3

    veto_turns = [t for t in session.turns if t.turn_type == TurnType.LEGIS_VETO]
    assert [t.round_number for t in veto_turns] == [1, 2, 3]


@pytest.mark.asyncio
async def test_legis_receives_target_semester_in_veto_context(
    students_repo: StudentRepository,
    courses_repo: CourseRepository,
) -> None:
    """Regression guard: Orchestrator must inject target_semester into
    Legis.can_veto so it retrieves fall rules — not summer — when the
    student asks for a fall schedule.
    """
    orch = _FakeOrchestrator(
        intent="build_schedule", target_hours=15, target_semester="fall-2026"
    )
    planner = _FakePlanner(
        lambda n: _proposal_for_round(n, student_id="442001234", semester="fall-2026")
    )
    legis = _FakeLegis(veto_sequence=[None])

    await run_negotiation(
        user_request="ابني لي جدول الفصل القادم",
        student_id="442001234",
        orchestrator=orch,  # type: ignore[arg-type]
        planner=planner,  # type: ignore[arg-type]
        legis=legis,  # type: ignore[arg-type]
        students=students_repo,
        courses=courses_repo,
    )

    assert len(legis.veto_calls) == 1
    call = legis.veto_calls[0]
    ctx = call["context"]
    assert ctx is not None, "Legis.can_veto must receive a VetoContext"
    assert ctx.target_semester == "fall-2026"
    assert ctx.student.student_id == "442001234"
    assert ctx.round_number == 1
    assert ctx.prior_objections == []
