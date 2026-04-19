"""Deterministic schedule-building logic — pure Python, no LLM, no I/O."""
from mokn.planning.conflicts import (
    find_conflicts,
    sections_conflict,
    times_overlap,
    total_credits,
    weighted_difficulty,
)
from mokn.planning.errors import InsufficientCoursesError
from mokn.planning.optimizer import HardConstraints, generate_schedule_candidates

__all__ = [
    "HardConstraints",
    "InsufficientCoursesError",
    "find_conflicts",
    "generate_schedule_candidates",
    "sections_conflict",
    "times_overlap",
    "total_credits",
    "weighted_difficulty",
]
