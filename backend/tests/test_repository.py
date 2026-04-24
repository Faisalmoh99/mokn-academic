"""Repository tests against the shipped mock JSON."""
from __future__ import annotations

from pathlib import Path

import pytest

from mokn.data.repository import (
    CourseNotFound,
    CourseRepository,
    StudentNotFound,
    StudentRepository,
)

_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "mock"


@pytest.fixture
def students_repo() -> StudentRepository:
    return StudentRepository(_DATA_DIR / "students.json")


@pytest.fixture
def courses_repo() -> CourseRepository:
    return CourseRepository(_DATA_DIR / "courses.json")


@pytest.mark.asyncio
async def test_student_get_by_id(students_repo: StudentRepository) -> None:
    student = await students_repo.get("442001234")
    assert student.name == "فيصل محمد العتيبي"
    assert student.gpa == 3.2


@pytest.mark.asyncio
async def test_student_not_found_raises(students_repo: StudentRepository) -> None:
    with pytest.raises(StudentNotFound):
        await students_repo.get("000000000")


@pytest.mark.asyncio
async def test_list_all_students(students_repo: StudentRepository) -> None:
    students = await students_repo.list_all()
    assert len(students) == 5


@pytest.mark.asyncio
async def test_course_get_by_code(courses_repo: CourseRepository) -> None:
    course = await courses_repo.get("CS201")
    assert course.prerequisites == ["CS101"]
    assert course.credits == 3


@pytest.mark.asyncio
async def test_course_not_found_raises(courses_repo: CourseRepository) -> None:
    with pytest.raises(CourseNotFound):
        await courses_repo.get("BIO999")


@pytest.mark.asyncio
async def test_list_available_requires_prereqs(courses_repo: CourseRepository) -> None:
    # A student who finished only CS101 + MATH101 is eligible for CS201 (CS101),
    # CS202 (CS101), MATH201 (MATH101) — but NOT CS301 (needs CS201).
    completed = {"CS101", "MATH101"}
    available = await courses_repo.list_available(completed)
    codes = {c.code for c in available}
    assert {"CS201", "CS202", "MATH201"}.issubset(codes)
    assert "CS301" not in codes
    assert "CS101" not in codes  # already done


@pytest.mark.asyncio
async def test_list_for_semester_filters(courses_repo: CourseRepository) -> None:
    fall = await courses_repo.list_for_semester("fall-2026")
    assert all("fall" in c.offered_semesters for c in fall)
    spring_only = await courses_repo.list_for_semester("spring")
    codes = {c.code for c in spring_only}
    assert "CS403" in codes  # spring-only in our catalog


@pytest.mark.asyncio
async def test_update_notes_appends_in_memory(students_repo: StudentRepository) -> None:
    await students_repo.update_notes("442001234", "ملاحظة تجريبية")
    student = await students_repo.get("442001234")
    assert "ملاحظة تجريبية" in student.memory_notes
