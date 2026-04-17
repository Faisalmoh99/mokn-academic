"""Course + Section schemas."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from mokn.schemas.student import WeekDay

Semester = Literal["fall", "spring", "summer"]

_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class CourseSection(BaseModel):
    section_id: str
    instructor: str
    days: list[WeekDay]
    start_time: str
    end_time: str
    capacity: int = Field(ge=1)
    enrolled: int = Field(ge=0)

    @field_validator("start_time", "end_time")
    @classmethod
    def _validate_time(cls, v: str) -> str:
        if not _TIME_RE.match(v):
            raise ValueError(f"time must be HH:MM 24h, got {v!r}")
        return v

    @property
    def has_space(self) -> bool:
        return self.enrolled < self.capacity


class Course(BaseModel):
    code: str
    name: str
    credits: int = Field(ge=1, le=6)
    prerequisites: list[str] = Field(default_factory=list)
    offered_semesters: list[Semester]
    sections: list[CourseSection]
    difficulty_level: int = Field(ge=1, le=5)
