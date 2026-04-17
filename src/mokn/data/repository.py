"""JSON-backed repositories for students and courses.

Exposed as async methods even though reads are local, so when Session 5
swaps the backend to Firestore no caller has to change.
"""
from __future__ import annotations

import asyncio
import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from mokn.schemas.course import Course, Semester
from mokn.schemas.student import Student


class StudentNotFound(KeyError):
    """Raised when a student_id doesn't exist in the repository."""


class CourseNotFound(KeyError):
    """Raised when a course code doesn't exist in the repository."""


_DEFAULT_DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "mock"


class StudentRepository:
    def __init__(self, json_path: Path | str) -> None:
        self._path = Path(json_path)
        self._cache: dict[str, Student] | None = None

    async def _load(self) -> dict[str, Student]:
        if self._cache is not None:
            return self._cache
        self._cache = await asyncio.to_thread(self._read)
        return self._cache

    def _read(self) -> dict[str, Student]:
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        students = [Student.model_validate(item) for item in raw]
        return {s.student_id: s for s in students}

    async def get(self, student_id: str) -> Student:
        data = await self._load()
        try:
            return data[student_id]
        except KeyError as exc:
            raise StudentNotFound(student_id) from exc

    async def list_all(self) -> list[Student]:
        data = await self._load()
        return list(data.values())

    async def update_notes(self, student_id: str, note: str) -> None:
        """In-memory note append. Persists only on explicit save (not yet wired)."""
        student = await self.get(student_id)
        student.memory_notes.append(note)


class CourseRepository:
    def __init__(self, json_path: Path | str) -> None:
        self._path = Path(json_path)
        self._cache: dict[str, Course] | None = None

    async def _load(self) -> dict[str, Course]:
        if self._cache is not None:
            return self._cache
        self._cache = await asyncio.to_thread(self._read)
        return self._cache

    def _read(self) -> dict[str, Course]:
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        courses = [Course.model_validate(item) for item in raw]
        return {c.code: c for c in courses}

    async def get(self, code: str) -> Course:
        data = await self._load()
        try:
            return data[code]
        except KeyError as exc:
            raise CourseNotFound(code) from exc

    async def list_all(self) -> list[Course]:
        data = await self._load()
        return list(data.values())

    async def list_for_semester(self, semester: str) -> list[Course]:
        """Filter by semester tag (fall/spring/summer)."""
        term = _normalize_semester(semester)
        courses = await self.list_all()
        return [c for c in courses if term in c.offered_semesters]

    async def list_available(self, completed: Iterable[str]) -> list[Course]:
        """Courses whose prereqs are all in the completed set."""
        done = set(completed)
        courses = await self.list_all()
        return [
            c
            for c in courses
            if c.code not in done and all(p in done for p in c.prerequisites)
        ]


def _normalize_semester(semester: str) -> Semester:
    s = semester.lower()
    for tag in ("fall", "spring", "summer"):
        if tag in s:
            return tag  # type: ignore[return-value]
    raise ValueError(f"unknown semester tag in {semester!r}")


@lru_cache(maxsize=1)
def get_student_repository() -> StudentRepository:
    return StudentRepository(_DEFAULT_DATA_DIR / "students.json")


@lru_cache(maxsize=1)
def get_course_repository() -> CourseRepository:
    return CourseRepository(_DEFAULT_DATA_DIR / "courses.json")


def _reset_repos_for_tests() -> None:  # pragma: no cover
    get_student_repository.cache_clear()
    get_course_repository.cache_clear()
