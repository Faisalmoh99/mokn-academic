"""BaseAgent — every autonomous agent in Mokn inherits this.

The negotiation protocol (Session 3) relies on two things being uniform
across agents: (1) `process(ctx) -> AgentResponse` for direct tasks, and
(2) `can_veto(proposal) -> VetoDecision | None` for reviewing another
agent's output. We keep both signatures here so Session 3 can wire them
through LangGraph without special-casing any agent.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from mokn.schemas.agent import AgentContext, AgentResponse, VetoDecision


class BaseAgent(ABC):
    """Abstract contract every Mokn agent implements."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short display name, e.g. 'Legis'. Must match AgentName literal."""

    @property
    @abstractmethod
    def role_description(self) -> str:
        """One-line Arabic description used in orchestrator prompts and logs."""

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """System prompt the agent hands to the LLM on every call."""

    @abstractmethod
    async def process(self, context: AgentContext) -> AgentResponse:
        """Handle a direct task routed to this agent."""

    async def can_veto(self, proposal: dict[str, Any]) -> VetoDecision | None:
        """Review a proposal from another agent.

        Return `None` when there's no objection. Return a `VetoDecision`
        when the proposal breaks a rule this agent owns. Base implementation
        abstains — override in subclasses that hold veto authority.
        """
        return None
