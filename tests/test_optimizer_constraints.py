"""HardConstraints behavior: the deterministic solver must respect them.

The original bug was that the solver had no notion of constraints, so a
Legis veto could not change the next proposal's credit count. These tests
lock that property in.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mokn.data.repository import CourseRepository, StudentRepository
from mokn.planning.optimizer import HardConstraints, generate_schedule_candidates

_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "mock"


@pytest.fixture
def students_repo() -> StudentRepository:
    return StudentRepository(_DATA_DIR / "students.json")


@pytest.fixture
def courses_repo() -> CourseRepository:
    return CourseRepository(_DATA_DIR / "courses.json")


@pytest.mark.asyncio
async def test_max_credits_caps_every_option(
    students_repo: StudentRepository, courses_repo: CourseRepository
) -> None:
    student = await students_repo.get("442001234")
    available = await courses_repo.list_available(student.completed_course_codes)
    fall = [c for c in available if "fall" in c.offered_semesters]

    options = await generate_schedule_candidates(
        student=student,
        available_courses=fall,
        target_hours=18,
        constraints=HardConstraints(max_credits=12),
    )

    assert options
    for opt in options:
        assert opt.total_credits <= 12, f"{opt.label} = {opt.total_credits} > 12"


@pytest.mark.asyncio
async def test_min_credits_floor_is_respected(
    students_repo: StudentRepository, courses_repo: CourseRepository
) -> None:
    student = await students_repo.get("442001234")
    available = await courses_repo.list_available(student.completed_course_codes)
    fall = [c for c in available if "fall" in c.offered_semesters]

    options = await generate_schedule_candidates(
        student=student,
        available_courses=fall,
        target_hours=9,
        constraints=HardConstraints(min_credits=12),
    )

    assert options, "expected the solver to find ≥12-credit options"
    for opt in options:
        assert opt.total_credits >= 12, f"{opt.label} = {opt.total_credits} < 12"


@pytest.mark.asyncio
async def test_excluded_courses_never_appear(
    students_repo: StudentRepository, courses_repo: CourseRepository
) -> None:
    student = await students_repo.get("442001234")
    available = await courses_repo.list_available(student.completed_course_codes)
    fall = [c for c in available if "fall" in c.offered_semesters]

    excluded = {fall[0].code}
    options = await generate_schedule_candidates(
        student=student,
        available_courses=fall,
        target_hours=15,
        constraints=HardConstraints(excluded_courses=excluded),
    )

    for opt in options:
        codes = {sc.course_code for sc in opt.courses}
        assert not (codes & excluded), f"{opt.label} contains an excluded course"


@pytest.mark.asyncio
async def test_no_constraints_matches_legacy_behavior(
    students_repo: StudentRepository, courses_repo: CourseRepository
) -> None:
    """Without constraints, output must match the pre-hotfix behavior so we
    haven't drifted accidentally."""
    student = await students_repo.get("442001234")
    available = await courses_repo.list_available(student.completed_course_codes)
    fall = [c for c in available if "fall" in c.offered_semesters]

    with_none = await generate_schedule_candidates(
        student=student, available_courses=fall, target_hours=15, constraints=None
    )
    with_empty = await generate_schedule_candidates(
        student=student,
        available_courses=fall,
        target_hours=15,
        constraints=HardConstraints(),
    )
    assert [o.label for o in with_none] == [o.label for o in with_empty]
    for a, b in zip(with_none, with_empty):
        assert a.total_credits == b.total_credits
        assert [c.course_code for c in a.courses] == [c.course_code for c in b.courses]
