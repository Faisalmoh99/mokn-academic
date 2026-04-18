"""Typed context the Orchestrator hands to an agent's `can_veto()`.

Legis needs more than the raw proposal to pick the right regulation chunk.
In particular `target_semester` disambiguates fall/spring/summer rules —
without it, Legis was retrieving summer articles when reviewing a fall
proposal. Prior objections let Legis avoid repeating the same veto if the
Planner has already partially complied.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from mokn.schemas.student import Student

ProposalType = Literal["schedule", "course_drop", "course_add"]


class VetoContext(BaseModel):
    """Side-channel context for an agent reviewing another agent's proposal."""

    student: Student
    target_semester: str = Field(
        ..., description="e.g. 'fall-2026' — drives regulation retrieval."
    )
    round_number: int = Field(default=1, ge=1)
    prior_objections: list[str] = Field(
        default_factory=list,
        description="Arabic strings of earlier veto reasons in the same session.",
    )
    proposal_type: ProposalType = "schedule"
