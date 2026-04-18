"""Negotiation protocol schemas.

Session 3 shape: Orchestrator opens a NegotiationSession, each turn in the
LangGraph loop is recorded as a NegotiationTurn, and the session closes with
an outcome + final Arabic answer for the student. Every turn carries a short
Arabic `summary` — that string is what the demo UI animates on screen.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from mokn.schemas.agent import AgentName
from mokn.schemas.schedule import ScheduleProposal


class TurnType(str, Enum):
    USER_REQUEST = "user_request"
    ORCHESTRATOR_CLASSIFY = "orchestrator_classify"
    PLANNER_PROPOSE = "planner_propose"
    LEGIS_REVIEW = "legis_review"
    LEGIS_VETO = "legis_veto"
    LEGIS_APPROVE = "legis_approve"
    ORCHESTRATOR_ROUTE = "orchestrator_route"
    ORCHESTRATOR_SYNTHESIZE = "orchestrator_synthesize"
    SYSTEM_ESCALATE = "system_escalate"
    SYSTEM_MAX_ROUNDS = "system_max_rounds"


class NegotiationOutcome(str, Enum):
    APPROVED = "approved"
    ESCALATED = "escalated"
    MAX_ROUNDS = "max_rounds"
    REGULATION_ONLY = "regulation_only"
    OUT_OF_SCOPE = "out_of_scope"


Intent = Literal["regulation_question", "build_schedule", "unknown"]


class NegotiationTurn(BaseModel):
    """A single utterance inside a negotiation session.

    `summary` is the demo-facing 1-line Arabic label — every turn must set it
    because the dashboard (Session 5) renders the session as a list of these.
    """

    turn_id: str = Field(default_factory=lambda: uuid4().hex)
    session_id: str
    round_number: int = Field(
        ge=0,
        description="0 for classification/fetch. 1+ for each propose→review cycle.",
    )
    turn_type: TurnType
    agent: AgentName | None = Field(
        default=None,
        description="None for USER_REQUEST and SYSTEM_* turns.",
    )
    content: dict[str, Any] = Field(default_factory=dict)
    summary: str = Field(..., description="1-line Arabic summary for the demo UI.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )


class NegotiationSession(BaseModel):
    """Full transcript of one Orchestrator-driven negotiation."""

    session_id: str = Field(default_factory=lambda: uuid4().hex)
    student_id: str | None = None
    user_request: str
    intent: Intent = "unknown"
    turns: list[NegotiationTurn] = Field(default_factory=list)
    outcome: NegotiationOutcome | None = None
    final_answer: str | None = None
    final_proposal: ScheduleProposal | None = None
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )
    ended_at: datetime | None = None
