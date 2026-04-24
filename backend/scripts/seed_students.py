#!/usr/bin/env python3
"""Validate the mock students + courses JSON against the Pydantic schemas.

Session 2 ships with hand-authored JSON; this script doesn't write anything,
it just proves the files parse and prints a summary. Session 5 will replace
this with Firestore seed logic.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from mokn.data.repository import CourseRepository, StudentRepository  # noqa: E402


async def main() -> None:
    root = Path(__file__).resolve().parents[1]
    students_repo = StudentRepository(root / "data" / "mock" / "students.json")
    courses_repo = CourseRepository(root / "data" / "mock" / "courses.json")

    students = await students_repo.list_all()
    courses = await courses_repo.list_all()

    print(f"✓ loaded {len(students)} students, {len(courses)} courses")
    print()
    print("الطلاب:")
    for s in students:
        print(
            f"  {s.student_id}  GPA={s.gpa:.1f}  "
            f"ساعات={s.completed_credits}/{s.total_credits_required}  {s.name}"
        )
    print()
    print("المواد:")
    for c in courses:
        prereq = ",".join(c.prerequisites) or "—"
        print(
            f"  {c.code:<8} ({c.credits}sh, diff={c.difficulty_level}) "
            f"prereqs=[{prereq}]  {c.name}"
        )


if __name__ == "__main__":
    asyncio.run(main())
