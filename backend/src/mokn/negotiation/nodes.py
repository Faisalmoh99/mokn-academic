"""LangGraph node factories for the negotiation loop.

Each public `make_*` function returns an async callable that LangGraph will
invoke with the current `NegotiationState` and expects a dict of partial
updates back. Keeping the graph wiring in factories (not class methods) keeps
the graph module itself declarative.

Every user-visible step emits a NegotiationTurn with a 1-line Arabic summary —
that string is what the demo dashboard animates on screen.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from uuid import uuid4

from mokn.agents.legis import LegisAgent
from mokn.agents.orchestrator import OrchestratorAgent
from mokn.agents.planner import PlannerAgent
from mokn.data.repository import CourseRepository, StudentNotFound, StudentRepository
from mokn.negotiation.state import NegotiationState
from mokn.planning.optimizer import HardConstraints
from mokn.schemas.agent import AgentContext, VetoDecision
from mokn.schemas.negotiation import NegotiationTurn, TurnType
from mokn.schemas.regulations import RegulationAnswer
from mokn.schemas.schedule import ScheduleOption, ScheduleProposal
from mokn.schemas.veto_context import VetoContext

logger = logging.getLogger(__name__)

NodeFn = Callable[[NegotiationState], Awaitable[dict[str, Any]]]
ConstraintsExtractor = Callable[[list[str]], Awaitable[HardConstraints]]

_MIN_TARGET_HOURS = 12
_HOUR_STEP_DOWN = 3


def _make_turn(
    *,
    session_id: str,
    round_number: int,
    turn_type: TurnType,
    agent: str | None,
    summary: str,
    content: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct a serialized NegotiationTurn (dict) ready to append to state."""
    turn = NegotiationTurn(
        turn_id=uuid4().hex,
        session_id=session_id,
        round_number=round_number,
        turn_type=turn_type,
        agent=agent,  # type: ignore[arg-type]
        content=content or {},
        summary=summary,
        timestamp=datetime.now(tz=timezone.utc),
    )
    return turn.model_dump(mode="json")


def _append_turn(state: NegotiationState, turn: dict[str, Any]) -> list[dict[str, Any]]:
    return [*state.get("turns", []), turn]


def make_user_request_turn(state: NegotiationState) -> dict[str, Any]:
    """Helper to seed the first turn. Called inline before graph.invoke."""
    return _make_turn(
        session_id=state["session_id"],
        round_number=0,
        turn_type=TurnType.USER_REQUEST,
        agent=None,
        summary=f"الطالب: {state['user_request']}",
        content={"request": state["user_request"]},
    )


# ---------------------------------------------------------------------------
# classify
# ---------------------------------------------------------------------------
def make_classify_node(orchestrator: OrchestratorAgent) -> NodeFn:
    async def classify(state: NegotiationState) -> dict[str, Any]:
        decision = await orchestrator.classify_intent(state["user_request"])
        summary_ar = {
            "regulation_question": "Orchestrator: سؤال عن اللوائح — سأحوّله إلى Legis.",
            "build_schedule": "Orchestrator: طلب بناء جدول — سأفتح تفاوضاً بين Planner و Legis.",
            "unknown": "Orchestrator: الطلب غير واضح — سأطلب توضيحاً.",
        }[decision.intent]
        turn = _make_turn(
            session_id=state["session_id"],
            round_number=0,
            turn_type=TurnType.ORCHESTRATOR_CLASSIFY,
            agent="Orchestrator",
            summary=summary_ar,
            content={
                "intent": decision.intent,
                "target_hours": decision.target_hours,
                "target_semester": decision.target_semester,
                "rationale": decision.rationale,
            },
        )
        return {
            "intent": decision.intent,
            "target_hours": decision.target_hours,
            "target_semester": decision.target_semester,
            "turns": _append_turn(state, turn),
        }

    return classify


# ---------------------------------------------------------------------------
# fetch_student
# ---------------------------------------------------------------------------
def make_fetch_student_node(students: StudentRepository) -> NodeFn:
    async def fetch_student(state: NegotiationState) -> dict[str, Any]:
        student_id = state.get("student_id")
        if not student_id:
            return {"student": None}
        try:
            student = await students.get(student_id)
        except StudentNotFound:
            logger.warning("negotiation: student %s not found", student_id)
            return {"student": None}
        return {"student": student}

    return fetch_student


# ---------------------------------------------------------------------------
# legis_only (regulation-question path)
# ---------------------------------------------------------------------------
def make_legis_only_node(legis: LegisAgent) -> NodeFn:
    async def legis_only(state: NegotiationState) -> dict[str, Any]:
        ctx = AgentContext(
            query=state["user_request"],
            student_id=state.get("student_id"),
        )
        response = await legis.process(ctx)
        answer = RegulationAnswer.model_validate(response.content)
        turn = _make_turn(
            session_id=state["session_id"],
            round_number=0,
            turn_type=TurnType.LEGIS_REVIEW,
            agent="Legis",
            summary=f"Legis: {_one_line(answer.answer)}",
            content=answer.model_dump(),
        )
        return {
            "legis_answer": answer.model_dump(),
            "outcome": "regulation_only",
            "turns": _append_turn(state, turn),
        }

    return legis_only


# ---------------------------------------------------------------------------
# planner_propose
# ---------------------------------------------------------------------------
def make_planner_propose_node(
    planner: PlannerAgent,
    *,
    constraints_extractor: ConstraintsExtractor | None = None,
) -> NodeFn:
    """Build the planner_propose node.

    `constraints_extractor` (when supplied) turns prior Legis objections into
    structured HardConstraints that the deterministic solver obeys. Without
    it, retries can only adjust the soft target_hours — which is what caused
    Planner to re-propose identical schedules round after round.
    """

    async def planner_propose(state: NegotiationState) -> dict[str, Any]:
        round_number = state.get("round_number", 0) + 1
        base_hours = state.get("target_hours") or 15
        objections = list(state.get("legis_objections", []))
        # Each retry trims the load by one course; Legis' most common veto is
        # the credit-hour cap, so this gives the next attempt a real chance.
        step_down = max(round_number - 1, 0) * _HOUR_STEP_DOWN
        adjusted_hours = max(base_hours - step_down, _MIN_TARGET_HOURS)

        constraints = HardConstraints()
        if round_number > 1 and objections and constraints_extractor is not None:
            constraints = await constraints_extractor(objections)
            # Clamp the soft target into the regulator's window so the
            # solver's strategies don't immediately fall back to defaults.
            if constraints.min_credits is not None:
                adjusted_hours = max(adjusted_hours, constraints.min_credits)
            if constraints.max_credits is not None:
                adjusted_hours = min(adjusted_hours, constraints.max_credits)

        metadata: dict[str, Any] = {
            "target_hours": adjusted_hours,
            "target_semester": state.get("target_semester") or "fall",
            "prior_objections": objections,
        }
        if not constraints.is_empty():
            metadata["hard_constraints"] = {
                "min_credits": constraints.min_credits,
                "max_credits": constraints.max_credits,
                "excluded_courses": sorted(constraints.excluded_courses),
                "required_courses": sorted(constraints.required_courses),
            }

        ctx = AgentContext(
            query=state["user_request"],
            student_id=state.get("student_id"),
            metadata=metadata,
        )
        response = await planner.process(ctx)
        proposal = ScheduleProposal.model_validate(response.content)
        if proposal.no_solution:
            summary = (
                "Planner: لا يوجد جدول يفي بالحد الأدنى — المواد المؤهلة للطالب غير كافية."
            )
        else:
            summary = (
                f"Planner: اقترح {_recommended_credits(proposal)} ساعة "
                f"(الخيار {proposal.recommended_option})."
            )
        turn = _make_turn(
            session_id=state["session_id"],
            round_number=round_number,
            turn_type=TurnType.PLANNER_PROPOSE,
            agent="Planner",
            summary=summary,
            content=proposal.model_dump(),
        )
        return {
            "current_proposal": proposal,
            "round_number": round_number,
            "turns": _append_turn(state, turn),
        }

    return planner_propose


# ---------------------------------------------------------------------------
# legis_review
# ---------------------------------------------------------------------------
def make_legis_review_node(legis: LegisAgent) -> NodeFn:
    async def legis_review(state: NegotiationState) -> dict[str, Any]:
        proposal = state.get("current_proposal")
        if proposal is None:
            # Shouldn't happen if the graph is wired correctly; guard anyway.
            return {}
        student = state.get("student")
        if student is None:
            return {}

        recommended = _pick_recommended_option(proposal)
        proposal_dict: dict[str, Any] = {
            "type": "schedule",
            "student": {
                "id": student.student_id,
                "gpa": student.gpa,
            },
            "target_semester": state.get("target_semester") or proposal.target_semester,
            "courses": [
                {"code": c.course_code, "credits": c.credits}
                for c in recommended.courses
            ],
            "total_credits": recommended.total_credits,
        }
        veto_ctx = VetoContext(
            student=student,
            target_semester=state.get("target_semester") or proposal.target_semester,
            round_number=state.get("round_number", 1),
            prior_objections=list(state.get("legis_objections", [])),
            proposal_type="schedule",
        )

        decision: VetoDecision | None = await legis.can_veto(
            proposal_dict, context=veto_ctx
        )

        if decision is None or (not decision.veto and not decision.violated_rules):
            turn = _make_turn(
                session_id=state["session_id"],
                round_number=state.get("round_number", 1),
                turn_type=TurnType.LEGIS_APPROVE,
                agent="Legis",
                summary="Legis: الجدول متوافق مع اللوائح — موافقة.",
                content={"veto": False},
            )
            return {
                "outcome": "approved",
                "turns": _append_turn(state, turn),
            }

        objections = list(state.get("legis_objections", []))
        objections.append(decision.reason)
        turn = _make_turn(
            session_id=state["session_id"],
            round_number=state.get("round_number", 1),
            turn_type=TurnType.LEGIS_VETO,
            agent="Legis",
            summary=f"Legis اعترض: {_one_line(decision.reason)}",
            content=decision.model_dump(),
        )
        return {
            "legis_objections": objections,
            "turns": _append_turn(state, turn),
        }

    return legis_review


# ---------------------------------------------------------------------------
# synthesize
# ---------------------------------------------------------------------------
def make_synthesize_node(orchestrator: OrchestratorAgent) -> NodeFn:
    async def synthesize(state: NegotiationState) -> dict[str, Any]:
        intent = state.get("intent", "unknown")
        outcome = state.get("outcome")
        round_number = state.get("round_number", 0)
        max_rounds = state.get("max_rounds", 3)

        # Resolve terminal outcome if the review loop dropped us here.
        proposal_state = state.get("current_proposal")
        no_solution = _is_no_solution(proposal_state)
        if outcome is None:
            if intent == "unknown":
                outcome = "out_of_scope"
            elif intent == "regulation_question":
                outcome = "regulation_only"
            elif no_solution:
                outcome = "escalated"
            elif state.get("legis_objections") and round_number >= max_rounds:
                outcome = "escalated"
            else:
                outcome = "approved"

        legis_answer_obj = None
        raw = state.get("legis_answer")
        if raw:
            legis_answer_obj = RegulationAnswer.model_validate(raw)

        final_answer = await orchestrator.synthesize_final_answer(
            request=state["user_request"],
            outcome=outcome,
            round_number=round_number,
            proposal=state.get("current_proposal"),
            legis_answer=legis_answer_obj,
            legis_objections=list(state.get("legis_objections", [])),
            max_rounds=max_rounds,
        )
        summary_map = {
            "approved": "Orchestrator: الجدول جاهز — تم تأليف الرد النهائي.",
            "regulation_only": "Orchestrator: صاغ إجابة اللوائح للطالب.",
            "escalated": "Orchestrator: لم نتوصل لاتفاق — تصعيد إلى مرشد بشري.",
            "max_rounds": "Orchestrator: استنفدت الجولات — تصعيد إلى مرشد بشري.",
            "out_of_scope": "Orchestrator: الطلب خارج نطاق الإرشاد — طلب توضيح.",
        }
        if no_solution:
            summary = "Orchestrator: لا توجد مواد مؤهلة كافية — توجيه الطالب للمرشد."
        else:
            summary = summary_map.get(outcome, "Orchestrator: صياغة الرد النهائي.")
        turn = _make_turn(
            session_id=state["session_id"],
            round_number=round_number,
            turn_type=TurnType.ORCHESTRATOR_SYNTHESIZE,
            agent="Orchestrator",
            summary=summary,
            content={"final_answer": final_answer, "outcome": outcome},
        )
        return {
            "final_answer": final_answer,
            "outcome": outcome,
            "turns": _append_turn(state, turn),
        }

    return synthesize


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _pick_recommended_option(proposal: ScheduleProposal) -> ScheduleOption:
    for opt in proposal.options:
        if opt.label == proposal.recommended_option:
            return opt
    return proposal.options[0]


def _recommended_credits(proposal: ScheduleProposal) -> int:
    return _pick_recommended_option(proposal).total_credits


def _one_line(text: str, *, limit: int = 120) -> str:
    clean = " ".join(text.strip().split())
    return clean if len(clean) <= limit else clean[: limit - 1] + "…"


def _is_no_solution(proposal: Any) -> bool:
    if proposal is None:
        return False
    if isinstance(proposal, dict):
        return bool(proposal.get("no_solution"))
    return bool(getattr(proposal, "no_solution", False))
