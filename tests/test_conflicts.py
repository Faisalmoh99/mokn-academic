"""Pure-logic tests for planning/conflicts.

These must stay fast (<50ms total) — no I/O, no fixtures beyond factory funcs.
"""
from __future__ import annotations

from mokn.planning.conflicts import (
    find_conflicts,
    sections_conflict,
    times_overlap,
    total_credits,
    weighted_difficulty,
)
from mokn.schemas.course import Course, CourseSection


def _section(
    sid: str,
    days: list[str],
    start: str,
    end: str,
    capacity: int = 30,
    enrolled: int = 10,
) -> CourseSection:
    return CourseSection(
        section_id=sid,
        instructor="د. تجربة",
        days=days,  # type: ignore[arg-type]
        start_time=start,
        end_time=end,
        capacity=capacity,
        enrolled=enrolled,
    )


def _course(code: str, credits: int, difficulty: int) -> Course:
    return Course(
        code=code,
        name=code,
        credits=credits,
        prerequisites=[],
        offered_semesters=["fall"],
        sections=[_section("101", ["sunday"], "08:00", "09:30")],
        difficulty_level=difficulty,
    )


def test_times_overlap_same_day_same_time() -> None:
    assert times_overlap(["sunday"], "10:00", "11:30", ["sunday"], "10:00", "11:30") is True


def test_times_overlap_different_days_no_conflict() -> None:
    assert times_overlap(["sunday"], "10:00", "11:30", ["monday"], "10:00", "11:30") is False


def test_times_overlap_same_day_disjoint_windows() -> None:
    assert times_overlap(["sunday"], "08:00", "09:30", ["sunday"], "10:00", "11:30") is False


def test_times_overlap_back_to_back_not_conflict() -> None:
    # 10:00-11:00 and 11:00-12:00 share sunday but the windows just touch.
    assert times_overlap(["sunday"], "10:00", "11:00", ["sunday"], "11:00", "12:00") is False


def test_times_overlap_partial_overlap_same_day() -> None:
    assert times_overlap(["sunday"], "10:00", "11:30", ["sunday"], "11:00", "12:30") is True


def test_find_conflicts_reports_pair_indices() -> None:
    a = _section("A", ["sunday"], "10:00", "11:30")
    b = _section("B", ["sunday"], "11:00", "12:30")  # conflicts with A
    c = _section("C", ["monday"], "10:00", "11:30")  # clean
    conflicts = find_conflicts([a, b, c])
    assert conflicts == [(0, 1)]


def test_sections_conflict_helper_matches_times_overlap() -> None:
    a = _section("A", ["sunday", "tuesday"], "10:00", "11:30")
    b = _section("B", ["tuesday"], "10:30", "11:00")
    assert sections_conflict(a, b) is True


def test_total_credits_sums() -> None:
    courses = [_course("CS101", 3, 2), _course("MATH101", 4, 3)]
    assert total_credits(courses) == 7


def test_weighted_difficulty_weighted_by_credits() -> None:
    # (3*2 + 4*4) / (3+4) = (6 + 16) / 7 = 22/7 ≈ 3.1428
    courses = [_course("CS101", 3, 2), _course("MATH201", 4, 4)]
    assert abs(weighted_difficulty(courses) - 22 / 7) < 1e-6


def test_weighted_difficulty_empty_returns_zero() -> None:
    assert weighted_difficulty([]) == 0.0
