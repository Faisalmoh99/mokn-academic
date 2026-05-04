"""Deterministic risk-detection rules. No LLM involved.

Why pure functions:
- Reproducible: same student → same factors, every time.
- Testable: 100% coverage with simple unit tests, no mocks.
- Defensible: judges can read this file and know exactly what triggers a flag.

The Guardian agent later wraps these factors in Arabic prose, but it never
*invents* factors — only the rules below decide who is at risk.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from mokn.schemas.guardian import RiskAssessment, RiskFactor, RiskSeverity
from mokn.schemas.student import CompletedCourse, Student

# Attendance thresholds: the regulation cap is `limit` per course (typically
# 25% of sessions). We escalate as the student approaches it.
_ATTENDANCE_HIGH_RATIO = 0.5      # ≥50% of allowed absences → MEDIUM
_ATTENDANCE_HIGHER_RATIO = 0.75   # ≥75% of allowed absences → HIGH
_ATTENDANCE_CRITICAL_RATIO = 1.0  # ≥100% → CRITICAL (already over the cap)

# Weak grade severity per letter. Anything below D is treated as F.
_WEAK_GRADE_SEVERITY: dict[str, RiskSeverity] = {
    "C+": RiskSeverity.LOW,
    "C": RiskSeverity.LOW,
    "D+": RiskSeverity.MEDIUM,
    "D": RiskSeverity.MEDIUM,
    "F": RiskSeverity.HIGH,
}

# GPA decline thresholds (in raw GPA points, drop vs prior semester).
_GPA_DECLINE_MIN = 0.3
_GPA_DECLINE_HIGH = 0.6

# Overload risk: only flagged if BOTH conditions met.
_OVERLOAD_GPA_FLOOR = 2.5
_OVERLOAD_HOURS_TRIGGER = 12  # > 12 with low GPA is risky

_GRADE_TO_POINTS: dict[str, float] = {
    "A+": 5.0,
    "A": 4.75,
    "B+": 4.5,
    "B": 4.0,
    "C+": 3.5,
    "C": 3.0,
    "D+": 2.5,
    "D": 2.0,
    "F": 1.0,
}


def detect_attendance_risks(student: Student) -> list[RiskFactor]:
    """Flag courses where absences approach (or exceed) the regulation limit.

    Reads `student.attendance` directly — that's where the existing data
    layer keeps absences/limit per course code.
    """
    factors: list[RiskFactor] = []
    for course_code, record in student.attendance.items():
        if record.limit <= 0:
            continue
        ratio = record.absences / record.limit
        severity, factor_type = _attendance_severity(ratio)
        if severity is None or factor_type is None:
            continue
        pct = round(ratio * 100)
        factors.append(
            RiskFactor(
                factor_type=factor_type,
                course_code=course_code,
                description_ar=(
                    f"غياب مرتفع في {course_code}: "
                    f"{record.absences} من أصل {record.limit} ({pct}% من الحد المسموح)."
                ),
                severity=severity,
                evidence={
                    "absences": record.absences,
                    "limit": record.limit,
                    "ratio": round(ratio, 3),
                },
            )
        )
    return factors


def detect_weak_grades(student: Student) -> list[RiskFactor]:
    """Flag any completed course graded C+ or below.

    We surface the most recent occurrences first by walking semesters in
    descending order so the LLM has the freshest evidence to cite.
    """
    factors: list[RiskFactor] = []
    for course in _completed_sorted_recent_first(student.courses_completed):
        severity = _WEAK_GRADE_SEVERITY.get(course.grade)
        if severity is None:
            continue
        factors.append(
            RiskFactor(
                factor_type="weak_grade",
                course_code=course.code,
                description_ar=(
                    f"تقدير {course.grade} في {course.code} ({course.name}) — "
                    f"فصل {course.semester}."
                ),
                severity=severity,
                evidence={
                    "grade": course.grade,
                    "semester": course.semester,
                    "credits": course.credits,
                },
            )
        )
    return factors


def detect_gpa_decline(student: Student) -> list[RiskFactor]:
    """Flag a GPA drop ≥ 0.3 between the two most recent semesters.

    The Student schema doesn't carry an explicit `prior_semester_gpa` field,
    so we derive per-semester GPA from `courses_completed` (weighted by
    credits) and compare the two most recent terms with at least one course
    each.
    """
    by_semester = _group_completed_by_semester(student.courses_completed)
    if len(by_semester) < 2:
        return []

    # Most recent first. Semester strings look like "441-2", "442-1" — sortable.
    semesters_sorted = sorted(by_semester.keys(), reverse=True)
    current_term, prior_term = semesters_sorted[0], semesters_sorted[1]
    current_gpa = _weighted_gpa(by_semester[current_term])
    prior_gpa = _weighted_gpa(by_semester[prior_term])
    drop = prior_gpa - current_gpa
    if drop < _GPA_DECLINE_MIN:
        return []

    severity = (
        RiskSeverity.HIGH if drop >= _GPA_DECLINE_HIGH else RiskSeverity.MEDIUM
    )
    return [
        RiskFactor(
            factor_type="gpa_declining",
            course_code=None,
            description_ar=(
                f"تراجع المعدل الفصلي من {prior_gpa:.2f} في {prior_term} "
                f"إلى {current_gpa:.2f} في {current_term} (انخفاض {drop:.2f})."
            ),
            severity=severity,
            evidence={
                "prior_semester": prior_term,
                "prior_gpa": round(prior_gpa, 2),
                "current_semester": current_term,
                "current_gpa": round(current_gpa, 2),
                "drop": round(drop, 2),
            },
        )
    ]


def detect_prior_dn(student: Student) -> list[RiskFactor]:
    """Flag a prior denial-for-absence (DN) when surfaced via memory notes.

    The current `Grade` literal cannot represent DN, so the data layer
    records it in `memory_notes` instead. We detect either the literal "DN"
    token or the Arabic phrase "حرمان"/"محروم"; both are how human advisors
    write this in practice.
    """
    needles = ("DN", "محروم", "حرمان")
    matches = [note for note in student.memory_notes if any(n in note for n in needles)]
    if not matches:
        return []
    return [
        RiskFactor(
            factor_type="prior_dn",
            course_code=None,
            description_ar="ملاحظة سابقة عن قرب الحرمان أو حرمان فعلي: " + matches[0],
            severity=RiskSeverity.HIGH,
            evidence={"matching_notes": matches},
        )
    ]


def detect_overload_risk(
    student: Student, target_hours: int | None = None
) -> list[RiskFactor]:
    """Flag a low-GPA student requesting (or carrying) too many hours.

    `target_hours` is None during routine scans — we only flag overload when
    Guardian is invoked in the context of a known schedule request.
    """
    if target_hours is None:
        return []
    if student.gpa >= _OVERLOAD_GPA_FLOOR or target_hours <= _OVERLOAD_HOURS_TRIGGER:
        return []
    return [
        RiskFactor(
            factor_type="low_gpa_high_load",
            course_code=None,
            description_ar=(
                f"المعدل التراكمي {student.gpa:.2f} منخفض، والعبء المطلوب "
                f"{target_hours} ساعة قد يكون أكبر من المناسب."
            ),
            severity=RiskSeverity.MEDIUM,
            evidence={
                "gpa": round(student.gpa, 2),
                "target_hours": target_hours,
            },
        )
    ]


def aggregate_severity(factors: list[RiskFactor]) -> RiskSeverity:
    """Combine factor severities into one overall severity for the student."""
    if not factors:
        return RiskSeverity.LOW

    counts: dict[RiskSeverity, int] = defaultdict(int)
    for f in factors:
        counts[f.severity] += 1

    if counts[RiskSeverity.CRITICAL] >= 1:
        return RiskSeverity.CRITICAL
    if counts[RiskSeverity.HIGH] >= 1:
        return RiskSeverity.HIGH
    if counts[RiskSeverity.MEDIUM] >= 1:
        return RiskSeverity.MEDIUM
    return RiskSeverity.LOW


def assess_student(
    student: Student, target_hours: int | None = None
) -> RiskAssessment:
    """Top-level: run every detector, aggregate, build a one-line summary."""
    factors = (
        detect_attendance_risks(student)
        + detect_weak_grades(student)
        + detect_gpa_decline(student)
        + detect_prior_dn(student)
        + detect_overload_risk(student, target_hours)
    )
    severity = aggregate_severity(factors)
    return RiskAssessment(
        student_id=student.student_id,
        student_name=student.name,
        overall_severity=severity,
        factors=factors,
        summary_ar=_build_summary_ar(student, factors, severity),
    )


def _attendance_severity(
    ratio: float,
) -> tuple[RiskSeverity | None, str | None]:
    if ratio >= _ATTENDANCE_CRITICAL_RATIO:
        return RiskSeverity.CRITICAL, "attendance_critical"
    if ratio >= _ATTENDANCE_HIGHER_RATIO:
        return RiskSeverity.HIGH, "attendance_high"
    if ratio >= _ATTENDANCE_HIGH_RATIO:
        return RiskSeverity.MEDIUM, "attendance_high"
    return None, None


def _completed_sorted_recent_first(
    courses: Iterable[CompletedCourse],
) -> list[CompletedCourse]:
    return sorted(courses, key=lambda c: c.semester, reverse=True)


def _group_completed_by_semester(
    courses: Iterable[CompletedCourse],
) -> dict[str, list[CompletedCourse]]:
    bucket: dict[str, list[CompletedCourse]] = defaultdict(list)
    for c in courses:
        bucket[c.semester].append(c)
    return dict(bucket)


def _weighted_gpa(courses: list[CompletedCourse]) -> float:
    total_points = 0.0
    total_credits = 0
    for c in courses:
        points = _GRADE_TO_POINTS.get(c.grade)
        if points is None:
            continue
        total_points += points * c.credits
        total_credits += c.credits
    return total_points / total_credits if total_credits else 0.0


def _build_summary_ar(
    student: Student, factors: list[RiskFactor], severity: RiskSeverity
) -> str:
    if not factors:
        return f"لا توجد مؤشرات خطر حالياً لـ {student.name}."
    severity_ar = {
        RiskSeverity.LOW: "منخفض",
        RiskSeverity.MEDIUM: "متوسط",
        RiskSeverity.HIGH: "مرتفع",
        RiskSeverity.CRITICAL: "حرج",
    }[severity]
    return (
        f"{student.name}: مستوى المخاطرة {severity_ar} "
        f"بناءً على {len(factors)} مؤشر."
    )


__all__ = [
    "aggregate_severity",
    "assess_student",
    "detect_attendance_risks",
    "detect_gpa_decline",
    "detect_overload_risk",
    "detect_prior_dn",
    "detect_weak_grades",
]
