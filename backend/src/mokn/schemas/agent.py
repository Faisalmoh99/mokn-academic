"""Shared agent contracts.

Every agent speaks in AgentContext/AgentResponse to the Orchestrator, and
optionally emits a VetoDecision when reviewing another agent's proposal.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

AgentName = Literal["Orchestrator", "Legis", "Planner", "Guardian"]


class AgentContext(BaseModel):
    """Everything an agent needs to act on a single task.

    This is the message an agent receives from the Orchestrator during
    a negotiation turn. Future sessions will expand `session_memory` and
    `student_memory`; keep the shape stable.
    """

    query: str = Field(..., description="The user-facing or agent-facing prompt.")
    student_id: str | None = Field(
        default=None, description="Identifier for the student this task is about."
    )
    conversation_history: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Recent turns in the user-facing conversation.",
    )
    session_memory: dict[str, Any] = Field(
        default_factory=dict,
        description="Short-lived state shared across agents within a session.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Open-ended extras routed by the Orchestrator.",
    )


class AgentResponse(BaseModel):
    """An agent's reply to an AgentContext.

    `content` is always a Pydantic model serialized to dict — never a raw
    string — so the Orchestrator can route it without re-parsing.
    """

    agent: AgentName
    content: dict[str, Any] = Field(
        ..., description="Structured payload from the agent's domain schema."
    )
    reasoning: str | None = Field(
        default=None,
        description="Optional short Arabic explanation of how the agent arrived here.",
    )
    confidence: Literal["high", "medium", "low"] = "medium"
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )


class VetoDecision(BaseModel):
    """An objection raised by one agent against another's proposal.

    `can_veto` returns `None` when the agent has no objection. A populated
    VetoDecision means the proposal should be rejected or reworked.
    """

    agent: AgentName
    veto: bool = Field(
        default=True,
        description="True when the proposal is rejected; False for a soft warning.",
    )
    reason: str = Field(..., description="Arabic explanation for the objection.")
    violated_rules: list[str] = Field(
        default_factory=list,
        description="Rule identifiers or short labels for what was violated.",
    )
    suggestion: str | None = Field(
        default=None,
        description="Optional counter-proposal to help the other agent recover.",
    )
