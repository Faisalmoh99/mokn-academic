"""LangGraph state for the negotiation loop.

LangGraph requires a TypedDict (not a Pydantic model) for its state because
it merges partial updates returned from each node. We use Pydantic models
only when we hand values back over the HTTP surface.

`turns` is a list of serialized NegotiationTurn dicts — LangGraph doesn't
need to know the concrete type, and keeping them as dicts keeps checkpointer
serialization trivial.
"""
from __future__ import annotations

from typing import Any, TypedDict

from mokn.schemas.schedule import ScheduleProposal
from mokn.schemas.student import Student


class NegotiationState(TypedDict, total=False):
    # Session identity + raw input.
    session_id: str
    student_id: str | None
    user_request: str

    # Classification output.
    intent: str  # "regulation_question" | "build_schedule" | "unknown"

    # Hydrated entities.
    student: Student | None

    # Planner targets.
    target_hours: int | None
    target_semester: str | None

    # Active proposal + cumulative objections.
    current_proposal: ScheduleProposal | None
    legis_objections: list[str]

    # Direct Legis path (for regulation_question intent).
    legis_answer: dict[str, Any] | None

    # Loop control.
    round_number: int
    max_rounds: int

    # Output.
    turns: list[dict[str, Any]]
    outcome: str | None
    final_answer: str | None
