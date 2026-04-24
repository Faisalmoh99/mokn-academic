"""Pure functions for time-conflict detection and schedule scoring.

Kept free of I/O and LLM calls so they stay deterministic and fast to test.
"""
from __future__ import annotations

from mokn.schemas.course import Course, CourseSection


def _to_minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def times_overlap(
    days_a: list[str],
    start_a: str,
    end_a: str,
    days_b: list[str],
    start_b: str,
    end_b: str,
) -> bool:
    """Two time windows conflict iff they share at least one day AND the
    [start, end) intervals overlap on that day. Back-to-back (10–11 then
    11–12) is explicitly NOT a conflict.
    """
    shared_days = set(days_a) & set(days_b)
    if not shared_days:
        return False
    a_start, a_end = _to_minutes(start_a), _to_minutes(end_a)
    b_start, b_end = _to_minutes(start_b), _to_minutes(end_b)
    return a_start < b_end and b_start < a_end


def sections_conflict(a: CourseSection, b: CourseSection) -> bool:
    return times_overlap(a.days, a.start_time, a.end_time, b.days, b.start_time, b.end_time)


def find_conflicts(sections: list[CourseSection]) -> list[tuple[int, int]]:
    """Return index pairs (i, j) with i < j where sections[i] conflicts with sections[j]."""
    conflicts: list[tuple[int, int]] = []
    for i in range(len(sections)):
        for j in range(i + 1, len(sections)):
            if sections_conflict(sections[i], sections[j]):
                conflicts.append((i, j))
    return conflicts


def total_credits(courses: list[Course]) -> int:
    return sum(c.credits for c in courses)


def weighted_difficulty(courses: list[Course]) -> float:
    """Credit-weighted average difficulty. Returns 0 for an empty list."""
    credits = total_credits(courses)
    if credits == 0:
        return 0.0
    weighted_sum = sum(c.difficulty_level * c.credits for c in courses)
    return weighted_sum / credits
