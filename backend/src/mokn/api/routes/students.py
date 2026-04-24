"""Student profile endpoint — powers the dashboard's Student Profile Card.

Read-only surface over the StudentRepository. The dashboard fetches this
on every scenario run so judges can see *which* student the agents are
reasoning about, not just the schedule output.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from mokn.api.deps import StudentRepoDep
from mokn.data.repository import StudentNotFound
from mokn.schemas.student import Student

router = APIRouter(prefix="/api/students", tags=["students"])


GpaTier = str  # "excellent" | "good" | "average" | "at_risk"


class AcademicProgress(BaseModel):
    completed_credits: int
    total_credits_required: int
    completed_percentage: float = Field(ge=0, le=100)
    remaining_credits: int


class AcademicHealth(BaseModel):
    gpa: float
    gpa_tier: GpaTier
    at_risk_courses: list[str]
    memory_notes: list[str]


class StudentProfile(BaseModel):
    student_id: str
    name: str
    major: str
    progress: AcademicProgress
    academic_health: AcademicHealth


@router.get("/{student_id}/profile", response_model=StudentProfile)
async def get_student_profile(
    student_id: str,
    students: StudentRepoDep,
) -> StudentProfile:
    try:
        student = await students.get(student_id)
    except StudentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student {student_id} not found",
        ) from exc
    return _to_profile(student)


def _to_profile(student: Student) -> StudentProfile:
    total = student.total_credits_required
    percentage = (student.completed_credits / total * 100) if total else 0.0
    at_risk = [
        code
        for code, att in student.attendance.items()
        if att.rate >= 0.5
    ]
    return StudentProfile(
        student_id=student.student_id,
        name=student.name,
        major=student.major,
        progress=AcademicProgress(
            completed_credits=student.completed_credits,
            total_credits_required=total,
            completed_percentage=round(percentage, 1),
            remaining_credits=student.remaining_credits,
        ),
        academic_health=AcademicHealth(
            gpa=student.gpa,
            gpa_tier=_classify_gpa(student.gpa),
            at_risk_courses=at_risk,
            memory_notes=list(student.memory_notes),
        ),
    )


def _classify_gpa(gpa: float) -> GpaTier:
    if gpa >= 3.5:
        return "excellent"
    if gpa >= 3.0:
        return "good"
    if gpa >= 2.0:
        return "average"
    return "at_risk"
