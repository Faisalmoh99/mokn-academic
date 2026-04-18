"""LangGraph StateGraph assembly + top-level `run_negotiation` entrypoint.

The graph shape:

    classify ─┬─► legis_only ──────────────► synthesize ──► END
              ├─► fetch_student ──► planner_propose ──► legis_review
              │                                           │
              │                                   (approve│veto+max)
              │                                           ▼
              │                                        synthesize ──► END
              │                                           ▲
              │                              (veto & round<max)
              │                                           │
              │                                  planner_propose ◄────┘
              │
              └─► synthesize ──► END  (unknown / out-of-scope)

The cycle Planner ↔ Legis is what makes this "true multi-agent" — Planner
must revise in light of Legis' objection, Legis gets to see the revised
proposal, and only Orchestrator's synthesize step is terminal.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from langgraph.graph import END, StateGraph

from mokn.agents.legis import LegisAgent
from mokn.agents.orchestrator import OrchestratorAgent
from mokn.agents.planner import PlannerAgent
from mokn.data.repository import CourseRepository, StudentRepository
from mokn.negotiation.nodes import (
    make_classify_node,
    make_fetch_student_node,
    make_legis_only_node,
    make_legis_review_node,
    make_planner_propose_node,
    make_synthesize_node,
    make_user_request_turn,
)
from mokn.negotiation.routing import route_after_classify, route_after_review
from mokn.negotiation.state import NegotiationState
from mokn.schemas.negotiation import (
    Intent,
    NegotiationOutcome,
    NegotiationSession,
    NegotiationTurn,
)
from mokn.schemas.schedule import ScheduleProposal


def build_negotiation_graph(
    *,
    orchestrator: OrchestratorAgent,
    planner: PlannerAgent,
    legis: LegisAgent,
    students: StudentRepository,
    courses: CourseRepository,  # reserved for future nodes (out-of-semester hints, etc.)
) -> Any:
    """Compile the cyclic Planner↔Legis graph with Orchestrator at the ends."""
    graph: StateGraph = StateGraph(NegotiationState)

    graph.add_node("classify", make_classify_node(orchestrator))
    graph.add_node("fetch_student", make_fetch_student_node(students))
    graph.add_node("legis_only", make_legis_only_node(legis))
    graph.add_node("planner_propose", make_planner_propose_node(planner))
    graph.add_node("legis_review", make_legis_review_node(legis))
    graph.add_node("synthesize", make_synthesize_node(orchestrator))

    graph.set_entry_point("classify")
    graph.add_conditional_edges(
        "classify",
        route_after_classify,
        {
            "legis_only": "legis_only",
            "fetch_student": "fetch_student",
            "synthesize": "synthesize",
        },
    )
    graph.add_edge("fetch_student", "planner_propose")
    graph.add_edge("planner_propose", "legis_review")
    graph.add_conditional_edges(
        "legis_review",
        route_after_review,
        {
            "planner_propose": "planner_propose",
            "synthesize": "synthesize",
        },
    )
    graph.add_edge("legis_only", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile()


async def run_negotiation(
    *,
    user_request: str,
    student_id: str | None,
    orchestrator: OrchestratorAgent,
    planner: PlannerAgent,
    legis: LegisAgent,
    students: StudentRepository,
    courses: CourseRepository,
    max_rounds: int = 3,
    session_id: str | None = None,
    recursion_limit: int = 25,
) -> NegotiationSession:
    """Run one full negotiation end-to-end and return a typed NegotiationSession."""
    from uuid import uuid4

    sid = session_id or uuid4().hex
    initial: NegotiationState = {
        "session_id": sid,
        "student_id": student_id,
        "user_request": user_request,
        "intent": "unknown",
        "student": None,
        "target_hours": None,
        "target_semester": None,
        "current_proposal": None,
        "legis_objections": [],
        "legis_answer": None,
        "round_number": 0,
        "max_rounds": max_rounds,
        "turns": [make_user_request_turn(
            {"session_id": sid, "user_request": user_request}  # type: ignore[arg-type]
        )],
        "outcome": None,
        "final_answer": None,
    }
    compiled = build_negotiation_graph(
        orchestrator=orchestrator,
        planner=planner,
        legis=legis,
        students=students,
        courses=courses,
    )
    started_at = datetime.now(tz=timezone.utc)
    final_state = await compiled.ainvoke(
        initial, config={"recursion_limit": recursion_limit}
    )
    ended_at = datetime.now(tz=timezone.utc)

    return _to_session(
        state=final_state,
        student_id=student_id,
        started_at=started_at,
        ended_at=ended_at,
    )


def _to_session(
    *,
    state: dict[str, Any],
    student_id: str | None,
    started_at: datetime,
    ended_at: datetime,
) -> NegotiationSession:
    turns = [NegotiationTurn.model_validate(t) for t in state.get("turns", [])]

    raw_proposal = state.get("current_proposal")
    final_proposal: ScheduleProposal | None = None
    if raw_proposal is not None and state.get("outcome") == "approved":
        if isinstance(raw_proposal, ScheduleProposal):
            final_proposal = raw_proposal
        else:
            final_proposal = ScheduleProposal.model_validate(raw_proposal)

    intent_value = state.get("intent", "unknown")
    if intent_value not in {"regulation_question", "build_schedule", "unknown"}:
        intent_value = "unknown"
    intent: Intent = intent_value  # type: ignore[assignment]

    outcome_value = state.get("outcome")
    outcome = NegotiationOutcome(outcome_value) if outcome_value else None

    return NegotiationSession(
        session_id=state["session_id"],
        student_id=student_id,
        user_request=state["user_request"],
        intent=intent,
        turns=turns,
        outcome=outcome,
        final_answer=state.get("final_answer"),
        final_proposal=final_proposal,
        started_at=started_at,
        ended_at=ended_at,
    )
