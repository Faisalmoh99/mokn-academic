"""Schedule proposal schemas — Planner's structured output."""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


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
    """Planner's full output — a bundle of ranked options.

    When `no_solution=True`, `options` may be empty and `recommended_option`
    may be `""`. This is how the Planner says "I tried and the eligible
    catalog is too thin" instead of returning a fake empty schedule.
    """

    student_id: str
    target_semester: str
    options: list[ScheduleOption] = Field(default_factory=list, max_length=4)
    recommended_option: str = ""
    warnings: list[str] = Field(default_factory=list)
    constraints_considered: list[str] = Field(default_factory=list)
    no_solution: bool = False

    @model_validator(mode="after")
    def _require_options_unless_no_solution(self) -> "ScheduleProposal":
        if not self.no_solution and not self.options:
            raise ValueError("ScheduleProposal must have at least one option when no_solution=False")
        return self
