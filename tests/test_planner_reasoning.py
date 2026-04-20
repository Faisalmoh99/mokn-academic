"""Planner prompt-construction tests — guard against reasoning regressions.

We don't call Gemini here. The bet is that a prompt carrying the student's
actual weak grades, attendance, and preferences lets the LLM stop writing
"جدول متوازن". If the prompt ever drops that context again, these tests
scream.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mokn.agents.planner import (
    _build_ranking_prompt,
    _format_at_risk,
    _format_weak_grades,
)
from mokn.data.repository import StudentRepository
from mokn.schemas.schedule import ScheduleCourse, ScheduleOption

_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "mock"


@pytest.fixture
def students_repo() -> StudentRepository:
    return StudentRepository(_DATA_DIR / "students.json")


def _fake_options() -> list[ScheduleOption]:
    course = ScheduleCourse(
        course_code="CS301",
        course_name="تحليل الخوارزميات",
        section_id="S1",
        credits=3,
        days=["sunday", "tuesday"],
        start_time="09:00",
        end_time="10:20",
        instructor="د. أحمد",
    )
    return [
        ScheduleOption(
            label="safe",
            courses=[course],
            total_credits=12,
            estimated_difficulty=1.0,
            reasoning="",
        ),
        ScheduleOption(
            label="balanced",
            courses=[course],
            total_credits=15,
            estimated_difficulty=1.3,
            reasoning="",
        ),
        ScheduleOption(
            label="aggressive",
            courses=[course],
            total_credits=18,
            estimated_difficulty=1.6,
            reasoning="",
        ),
    ]


@pytest.mark.asyncio
async def test_prompt_mentions_gpa_and_progress(students_repo: StudentRepository) -> None:
    """Prompt carries the exact GPA and completed/total credits numerically."""
    student = await students_repo.get("442005678")
    prompt = _build_ranking_prompt(student, _fake_options(), 18, "fall-2026")
    assert "2.10" in prompt, "GPA must appear with two-decimal precision"
    assert "30/132" in prompt, "completed/total credits must appear verbatim"


@pytest.mark.asyncio
async def test_prompt_includes_memory_notes_when_present(
    students_repo: StudentRepository,
) -> None:
    student = await students_repo.get("442005678")
    prompt = _build_ranking_prompt(student, _fake_options(), 18, "fall-2026")
    # Each memory note should appear verbatim so the LLM can cite it.
    for note in student.memory_notes:
        assert note in prompt


@pytest.mark.asyncio
async def test_prompt_surfaces_at_risk_attendance(
    students_repo: StudentRepository,
) -> None:
    """Student 442009876 is 4/6 absences in CS201 — must be in the prompt."""
    student = await students_repo.get("442009876")
    prompt = _build_ranking_prompt(student, _fake_options(), 15, "fall-2026")
    assert "CS201" in prompt
    assert "4/6" in prompt
    assert "67%" in prompt


@pytest.mark.asyncio
async def test_prompt_surfaces_weak_grades(
    students_repo: StudentRepository,
) -> None:
    """CS101 D and MATH102 D+ should reach the LLM so it can reference them."""
    student = await students_repo.get("442005678")
    prompt = _build_ranking_prompt(student, _fake_options(), 18, "fall-2026")
    assert "CS101" in prompt
    assert "MATH102" in prompt


@pytest.mark.asyncio
async def test_prompt_distinguishes_two_students(
    students_repo: StudentRepository,
) -> None:
    """Same request, different students — prompts must diverge meaningfully."""
    weak_student = await students_repo.get("442005678")  # GPA 2.1, weak grades
    strong_student = await students_repo.get("442001234")  # GPA 3.2, clean record

    weak_prompt = _build_ranking_prompt(weak_student, _fake_options(), 15, "fall-2026")
    strong_prompt = _build_ranking_prompt(
        strong_student, _fake_options(), 15, "fall-2026"
    )

    assert weak_prompt != strong_prompt
    assert "2.10" in weak_prompt and "3.20" in strong_prompt
    # Weak student has documented struggles; strong student doesn't.
    assert "D+" in weak_prompt
    assert "D+" not in strong_prompt


@pytest.mark.asyncio
async def test_prompt_includes_prior_objections_when_supplied(
    students_repo: StudentRepository,
) -> None:
    """Legis rejections from prior rounds must reach the LLM so it can adjust."""
    student = await students_repo.get("442005678")
    objection = "المادة 14: تجاوز الحد الأقصى للساعات المسموح بها."
    prompt = _build_ranking_prompt(
        student, _fake_options(), 18, "fall-2026", prior_objections=[objection]
    )
    assert objection in prompt
    assert "Legis" in prompt


def test_format_weak_grades_empty_for_clean_record() -> None:
    """No C/D/F → empty string (not a fake 'لا يوجد' fallback here)."""
    import asyncio

    async def _run() -> str:
        repo = StudentRepository(_DATA_DIR / "students.json")
        student = await repo.get("442003456")  # GPA 3.9 all A's
        return _format_weak_grades(student)

    assert asyncio.run(_run()) == ""


def test_format_at_risk_threshold_is_50_percent() -> None:
    """Attendance is only flagged at >= 50% of the absence limit."""
    import asyncio

    async def _run() -> tuple[str, str]:
        repo = StudentRepository(_DATA_DIR / "students.json")
        flagged = await repo.get("442009876")  # 4/6 = 67%
        clean = await repo.get("442001234")  # no attendance data
        return _format_at_risk(flagged), _format_at_risk(clean)

    flagged, clean = asyncio.run(_run())
    assert "CS201" in flagged
    assert clean == ""
