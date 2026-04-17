"""Deterministic schedule-candidate builder.

Given a student and a list of courses they're eligible to take, emit up to
`max_options` distinct `ScheduleOption`s (safe / balanced / aggressive).

This module is deliberately dumb: no LLM, no probabilistic scoring. The
`PlannerAgent` wraps these candidates with Gemini-generated reasoning and
picks a recommendation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from mokn.planning.conflicts import sections_conflict, total_credits, weighted_difficulty
from mokn.schemas.course import Course, CourseSection
from mokn.schemas.schedule import ScheduleCourse, ScheduleOption
from mokn.schemas.student import Student, StudentPreferences


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
) -> ScheduleOption | None:
    ordered = sorted(eligible, key=strategy.sort_key)
    picked_courses: list[Course] = []
    picked_sections: list[CourseSection] = []
    picked_credits = 0

    for course in ordered:
        if picked_credits + course.credits > strategy.target_hours:
            continue
        section = _pick_section(course, picked_sections, prefs)
        if section is None:
            continue
        picked_courses.append(course)
        picked_sections.append(section)
        picked_credits += course.credits
        if picked_credits >= strategy.target_hours:
            break

    if not picked_courses:
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


def _strategies(target: int, max_options: int) -> list[_Strategy]:
    # Sort keys intentionally different per strategy so candidates diverge.
    safe = _Strategy(
        label="safe",
        target_hours=max(target - 3, 9),
        sort_key=lambda c: (c.difficulty_level, c.credits, c.code),
        reasoning="جدول متحفظ: أقل ساعات وأسهل مواد، مناسب للاحتياط.",
    )
    balanced = _Strategy(
        label="balanced",
        target_hours=target,
        sort_key=lambda c: (abs(c.difficulty_level - 3), c.credits, c.code),
        reasoning="جدول متوازن: يستهدف الساعات المطلوبة بتوزيع صعوبة معتدل.",
    )
    aggressive = _Strategy(
        label="aggressive",
        target_hours=target + 3,
        sort_key=lambda c: (-c.difficulty_level, -c.credits, c.code),
        reasoning="جدول مكثف: ساعات أعلى ومواد أصعب، لتسريع التخرج.",
    )
    return [safe, balanced, aggressive][:max_options]


async def generate_schedule_candidates(
    student: Student,
    available_courses: list[Course],
    target_hours: int,
    max_options: int = 3,
) -> list[ScheduleOption]:
    """Return up to `max_options` schedule variants for `student`.

    `available_courses` must already be filtered to courses whose prereqs
    the student has met and which they haven't already completed — that's
    the repository's job, not ours.
    """
    if target_hours <= 0:
        return []

    options: list[ScheduleOption] = []
    seen_codes: set[tuple[str, ...]] = set()
    for strategy in _strategies(target_hours, max_options):
        option = _build_candidate(strategy, available_courses, student.preferences)
        if option is None:
            continue
        key = tuple(sorted(option.course_codes))
        if key in seen_codes:
            continue  # skip a strategy that collapsed into an existing candidate
        seen_codes.add(key)
        options.append(option)

    return options
