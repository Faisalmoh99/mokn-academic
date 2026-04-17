"""Negotiation protocol schemas.

Skeleton for Sessions 2-3: the Orchestrator opens a NegotiationSession,
each participating agent emits NegotiationTurns, and the session resolves
once all objections are addressed. Only the shapes are fixed here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from mokn.schemas.agent import AgentName


class TurnType(str, Enum):
    PROPOSE = "propose"
    OBJECT = "object"
    CLARIFY = "clarify"
    WITHDRAW = "withdraw"
    APPROVE = "approve"
    VETO = "veto"


class NegotiationTurn(BaseModel):
    """A single utterance by one agent inside a negotiation."""

    agent: AgentName
    type: TurnType
    content: dict[str, Any] = Field(
        ..., description="Structured payload for this turn (proposal, objection, etc.)."
    )
    references: list[str] = Field(
        default_factory=list,
        description="IDs of prior turns this one responds to, if any.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )
    turn_id: str = Field(default_factory=lambda: uuid4().hex)


class NegotiationSession(BaseModel):
    """A bounded multi-turn conversation between agents, driven by Orchestrator."""

    session_id: str = Field(default_factory=lambda: uuid4().hex)
    student_id: str | None = None
    topic: str = Field(..., description="Short label describing the negotiation goal.")
    participants: list[AgentName] = Field(default_factory=list)
    turns: list[NegotiationTurn] = Field(default_factory=list)
    status: str = Field(
        default="open",
        description="'open' while the debate continues, 'resolved' or 'escalated' at end.",
    )
    final_decision: dict[str, Any] | None = None
    opened_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )
