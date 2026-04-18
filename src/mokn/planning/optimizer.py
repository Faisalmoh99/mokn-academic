"""Deterministic schedule-candidate builder.

Given a student and a list of courses they're eligible to take, emit up to
`max_options` distinct `ScheduleOption`s (safe / balanced / aggressive).

This module is deliberately dumb: no LLM, no probabilistic scoring. The
`PlannerAgent` wraps these candidates with Gemini-generated reasoning and
picks a recommendation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from mokn.planning.conflicts import sections_conflict, total_credits, weighted_difficulty
from mokn.schemas.course import Course, CourseSection
from mokn.schemas.schedule import ScheduleCourse, ScheduleOption
from mokn.schemas.student import Student, StudentPreferences


@dataclass
class HardConstraints:
    """Structured constraints distilled from prior Legis vetoes.

    The deterministic solver treats these as inviolable: a candidate that
    violates any of them is not emitted. Without these, retries would just
    re-propose the rejected schedule.
    """

    min_credits: int | None = None
    max_credits: int | None = None
    excluded_courses: set[str] = field(default_factory=set)
    required_courses: set[str] = field(default_factory=set)

    def is_empty(self) -> bool:
        return (
            self.min_credits is None
            and self.max_credits is None
            and not self.excluded_courses
            and not self.required_courses
        )


@dataclass(frozen=True)
class _Strategy:
    label: str
    target_hours: int
    sort_key: Callable[[Course], tuple]
    reasoning: str


def _bucket_for_hour(hour: int) -> str:
    if hour < 12:
        return "morning"
    if hour < 16:
        return "afternoon"
    return "evening"


def _section_allowed(section: CourseSection, prefs: StudentPreferences) -> bool:
    """Hard filter: section is ruled out if it uses an avoided day or has no space."""
    if not section.has_space:
        return False
    if prefs.avoid_days and any(d in prefs.avoid_days for d in section.days):
        return False
    return True


def _section_score(section: CourseSection, prefs: StudentPreferences) -> float:
    """Soft score: higher = better match for the student's preferences."""
    score = 0.0
    start_hour = int(section.start_time.split(":")[0])
    bucket = _bucket_for_hour(start_hour)
    if prefs.preferred_times and bucket in prefs.preferred_times:
        score += 10.0
    # Prefer fuller but not-full sections (signal of good instructor / real offering).
    fill_ratio = section.enrolled / section.capacity if section.capacity else 0
    score += fill_ratio * 2
    return score


def _pick_section(
    course: Course,
    already_chosen: list[CourseSection],
    prefs: StudentPreferences,
) -> CourseSection | None:
    candidates = [s for s in course.sections if _section_allowed(s, prefs)]
    candidates.sort(key=lambda s: _section_score(s, prefs), reverse=True)
    for section in candidates:
        if any(sections_conflict(section, chosen) for chosen in already_chosen):
            continue
        return section
    return None


def _build_candidate(
    strategy: _Strategy,
    eligible: list[Course],
    prefs: StudentPreferences,
    constraints: HardConstraints | None = None,
) -> ScheduleOption | None:
    constraints = constraints or HardConstraints()
    pool = [c for c in eligible if c.code not in constraints.excluded_courses]
    required_codes = constraints.required_courses & {c.code for c in pool}
    required_first = sorted(
        (c for c in pool if c.code in required_codes), key=lambda c: c.code
    )
    rest = sorted((c for c in pool if c.code not in required_codes), key=strategy.sort_key)
    ordered = required_first + rest

    ceiling = strategy.target_hours
    if constraints.max_credits is not None:
        ceiling = min(ceiling, constraints.max_credits)
    floor = constraints.min_credits or 0

    picked_courses: list[Course] = []
    picked_sections: list[CourseSection] = []
    picked_credits = 0

    for course in ordered:
        if picked_credits + course.credits > ceiling:
            continue
        section = _pick_section(course, picked_sections, prefs)
        if section is None:
            continue
        picked_courses.append(course)
        picked_sections.append(section)
        picked_credits += course.credits
        if picked_credits >= max(strategy.target_hours, floor):
            break

    if not picked_courses:
        return None
    if picked_credits < floor:
        # Could not assemble enough courses to clear the regulator's floor.
        return None
    if required_codes and not required_codes.issubset({c.code for c in picked_courses}):
        return None

    schedule_courses = [
        ScheduleCourse(
            course_code=c.code,
            course_name=c.name,
            section_id=sec.section_id,
            credits=c.credits,
            days=list(sec.days),
            start_time=sec.start_time,
            end_time=sec.end_time,
            instructor=sec.instructor,
        )
        for c, sec in zip(picked_courses, picked_sections)
    ]

    return ScheduleOption(
        label=strategy.label,
        courses=schedule_courses,
        total_credits=total_credits(picked_courses),
        estimated_difficulty=round(weighted_difficulty(picked_courses), 2),
        reasoning=strategy.reasoning,
    )


def _clamp(value: int, *, low: int | None, high: int | None) -> int:
    if low is not None:
        value = max(value, low)
    if high is not None:
        value = min(value, high)
    return value


def _strategies(
    target: int, max_options: int, constraints: HardConstraints | None = None
) -> list[_Strategy]:
    constraints = constraints or HardConstraints()
    low, high = constraints.min_credits, constraints.max_credits

    safe_target = _clamp(max(target - 3, 9), low=low, high=high)
    balanced_target = _clamp(target, low=low, high=high)
    aggressive_target = _clamp(target + 3, low=low, high=high)

    # Sort keys intentionally different per strategy so candidates diverge.
    safe = _Strategy(
        label="safe",
        target_hours=safe_target,
        sort_key=lambda c: (c.difficulty_level, c.credits, c.code),
        reasoning="جدول متحفظ: أقل ساعات وأسهل مواد، مناسب للاحتياط.",
    )
    balanced = _Strategy(
        label="balanced",
        target_hours=balanced_target,
        sort_key=lambda c: (abs(c.difficulty_level - 3), c.credits, c.code),
        reasoning="جدول متوازن: يستهدف الساعات المطلوبة بتوزيع صعوبة معتدل.",
    )
    aggressive = _Strategy(
        label="aggressive",
        target_hours=aggressive_target,
        sort_key=lambda c: (-c.difficulty_level, -c.credits, c.code),
        reasoning="جدول مكثف: ساعات أعلى ومواد أصعب، لتسريع التخرج.",
    )
    return [safe, balanced, aggressive][:max_options]


async def generate_schedule_candidates(
    student: Student,
    available_courses: list[Course],
    target_hours: int,
    max_options: int = 3,
    constraints: HardConstraints | None = None,
) -> list[ScheduleOption]:
    """Return up to `max_options` schedule variants for `student`.

    `available_courses` must already be filtered to courses whose prereqs
    the student has met and which they haven't already completed — that's
    the repository's job, not ours.

    `constraints` are hard regulatory bounds derived from prior Legis
    vetoes. No emitted candidate may violate them — this is the lever that
    makes round 2 differ from round 1 when the regulator imposed a floor or
    ceiling on credits.
    """
    if target_hours <= 0:
        return []

    options: list[ScheduleOption] = []
    seen_codes: set[tuple[str, ...]] = set()
    for strategy in _strategies(target_hours, max_options, constraints):
        option = _build_candidate(
            strategy, available_courses, student.preferences, constraints
        )
        if option is None:
            continue
        key = tuple(sorted(option.course_codes))
        if key in seen_codes:
            continue  # skip a strategy that collapsed into an existing candidate
        seen_codes.add(key)
        options.append(option)

    return options
