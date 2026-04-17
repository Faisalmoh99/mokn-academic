"""Schedule proposal schemas — Planner's structured output."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ScheduleCourse(BaseModel):
    course_code: str
    course_name: str
    section_id: str
    credits: int = Field(ge=1, le=6)
    days: list[str]
    start_time: str
    end_time: str
    instructor: str


class ScheduleOption(BaseModel):
    """A single proposed schedule variant."""

    label: str  # e.g. "safe" / "balanced" / "aggressive"
    courses: list[ScheduleCourse]
    total_credits: int = Field(ge=0)
    estimated_difficulty: float = Field(ge=0)
    reasoning: str

    @property
    def course_codes(self) -> list[str]:
        return [c.course_code for c in self.courses]


class ScheduleProposal(BaseModel):
    """Planner's full output — a bundle of ranked options."""

    student_id: str
    target_semester: str
    options: list[ScheduleOption] = Field(min_length=1, max_length=4)
    recommended_option: str  # label of the recommended option
    warnings: list[str] = Field(default_factory=list)
    constraints_considered: list[str] = Field(default_factory=list)
