"""Solver fallback: relaxed-preference pass and InsufficientCoursesError.

Before this suite, the optimizer silently returned an empty list when
preferences (or a thin eligible pool) left nothing to propose. That empty
list got wrapped in a fake `ScheduleProposal` and handed to Legis, which
vetoed it for being below the credit-hour floor — and the loop restarted.

These tests lock in:
  1. When preferences block everything, the solver relaxes them instead of
     failing.
  2. When even the relaxed pass can't meet the floor, the solver raises
     `InsufficientCoursesError` — no fake empty schedule.
  3. The `no_solution` flag round-trips cleanly through `ScheduleProposal`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mokn.data.repository import CourseRepository, StudentRepository
from mokn.planning.errors import InsufficientCoursesError
from mokn.planning.optimizer import HardConstraints, generate_schedule_candidates
from mokn.schemas.schedule import ScheduleProposal
from mokn.schemas.student import Student, StudentPreferences

_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "mock"


@pytest.fixture
def students_repo() -> StudentRepository:
    return StudentRepository(_DATA_DIR / "students.json")


@pytest.fixture
def courses_repo() -> CourseRepository:
    return CourseRepository(_DATA_DIR / "courses.json")


@pytest.mark.asyncio
async def test_rich_pool_returns_options_above_floor(
    students_repo: StudentRepository, courses_repo: CourseRepository
) -> None:
    """Happy path: student with plenty of eligible courses → ≥1 option ≥12h."""
    student = await students_repo.get("442001234")
    available = await courses_repo.list_available(student.completed_course_codes)
    fall = [c for c in available if "fall" in c.offered_semesters]

    options = await generate_schedule_candidates(
        student=student, available_courses=fall, target_hours=15
    )

    assert options
    for opt in options:
        assert opt.total_credits >= 12, (
            f"{opt.label} below the 12-credit regulatory floor: {opt.total_credits}"
        )


@pytest.mark.asyncio
async def test_preferences_that_block_everything_trigger_relax_pass(
    students_repo: StudentRepository, courses_repo: CourseRepository
) -> None:
    """A student who avoids every weekday should still get a schedule.

    The first pass will filter out every section; the relaxed pass drops
    `avoid_days` and must succeed.
    """
    base = await students_repo.get("442001234")
    blocked = Student(
        **{
            **base.model_dump(),
            "preferences": StudentPreferences(
                preferred_times=[],
                avoid_days=["sunday", "monday", "tuesday", "wednesday", "thursday"],
                max_hours_per_day=None,
            ),
        }
    )
    available = await courses_repo.list_available(blocked.completed_course_codes)
    fall = [c for c in available if "fall" in c.offered_semesters]

    options = await generate_schedule_candidates(
        student=blocked, available_courses=fall, target_hours=15
    )

    assert options, "relaxed pass should have produced at least one option"
    for opt in options:
        assert opt.total_credits >= 12
        assert "تخفيف" in opt.reasoning, (
            "relaxed-pass options must signal that preferences were relaxed"
        )


@pytest.mark.asyncio
async def test_pool_too_thin_raises_insufficient_courses(
    students_repo: StudentRepository, courses_repo: CourseRepository
) -> None:
    """Feed the solver just one 3-credit course; it can't reach 12 → raises."""
    student = await students_repo.get("442001234")
    available = await courses_repo.list_available(student.completed_course_codes)
    fall = [c for c in available if "fall" in c.offered_semesters]
    tiny = [fall[0]]  # 3 credits total; can't meet the 12-credit floor

    with pytest.raises(InsufficientCoursesError) as exc_info:
        await generate_schedule_candidates(
            student=student, available_courses=tiny, target_hours=15
        )

    err = exc_info.value
    assert err.student_id == student.student_id
    assert err.eligible_credits == tiny[0].credits
    assert err.min_required == 12


@pytest.mark.asyncio
async def test_explicit_min_credits_beats_floor_default(
    students_repo: StudentRepository, courses_repo: CourseRepository
) -> None:
    """A caller-supplied min_credits of 6 must still be respected (bypasses 12)."""
    student = await students_repo.get("442001234")
    available = await courses_repo.list_available(student.completed_course_codes)
    fall = [c for c in available if "fall" in c.offered_semesters][:2]
    # Two 3-credit courses = 6 credits total. Default floor would reject; explicit floor=6 accepts.

    options = await generate_schedule_candidates(
        student=student,
        available_courses=fall,
        target_hours=6,
        constraints=HardConstraints(min_credits=6),
    )

    assert options
    for opt in options:
        assert opt.total_credits >= 6


@pytest.mark.asyncio
async def test_no_solution_flag_round_trips_through_schema() -> None:
    """ScheduleProposal must accept empty options when no_solution=True."""
    proposal = ScheduleProposal(
        student_id="x",
        target_semester="fall",
        options=[],
        recommended_option="",
        warnings=["w"],
        constraints_considered=[],
        no_solution=True,
    )
    round_tripped = ScheduleProposal.model_validate(proposal.model_dump())
    assert round_tripped.no_solution is True
    assert round_tripped.options == []

    # Sanity: same payload without no_solution must fail validation.
    with pytest.raises(ValueError):
        ScheduleProposal(
            student_id="x",
            target_semester="fall",
            options=[],
            recommended_option="",
        )
