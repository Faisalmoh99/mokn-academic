"""Student record schemas.

Backed by JSON in Session 2; the same shape will front Firestore in Session 5.
Keep these models strict: a malformed student file should fail at load time,
not silently blow up inside the Planner.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Grade = Literal["A+", "A", "B+", "B", "C+", "C", "D+", "D", "F"]
TimeOfDay = Literal["morning", "afternoon", "evening"]
WeekDay = Literal["sunday", "monday", "tuesday", "wednesday", "thursday"]


class CompletedCourse(BaseModel):
    code: str
    name: str
    grade: Grade
    semester: str  # e.g. "441-1"
    credits: int = Field(ge=1, le=6)


class AttendanceRecord(BaseModel):
    absences: int = Field(ge=0)
    limit: int = Field(ge=1)

    @property
    def rate(self) -> float:
        return self.absences / self.limit if self.limit > 0 else 0.0


class StudentPreferences(BaseModel):
    preferred_times: list[TimeOfDay] = Field(default_factory=list)
    avoid_days: list[WeekDay] = Field(default_factory=list)
    max_hours_per_day: int | None = None


class Student(BaseModel):
    student_id: str
    name: str
    major: str
    gpa: float = Field(ge=0, le=5)
    completed_credits: int = Field(ge=0)
    total_credits_required: int = Field(ge=1)
    courses_completed: list[CompletedCourse] = Field(default_factory=list)
    current_courses: list[str] = Field(default_factory=list)
    attendance: dict[str, AttendanceRecord] = Field(default_factory=dict)
    preferences: StudentPreferences = Field(default_factory=StudentPreferences)
    memory_notes: list[str] = Field(default_factory=list)

    @property
    def remaining_credits(self) -> int:
        return max(self.total_credits_required - self.completed_credits, 0)

    @property
    def completed_course_codes(self) -> set[str]:
        return {c.code for c in self.courses_completed}

    @property
    def max_absence_rate(self) -> float:
        """Worst absence rate across current courses; 0 if no attendance tracked."""
        if not self.attendance:
            return 0.0
        return max(rec.rate for rec in self.attendance.values())
