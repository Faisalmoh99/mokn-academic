"""Pure-function tests for the risk-rules layer.

These tests don't mock anything — risk rules are deterministic Python on
Pydantic models, which is the whole point.
"""
from __future__ import annotations

import pytest

from mokn.monitoring.risk_rules import (
    aggregate_severity,
    assess_student,
    detect_attendance_risks,
    detect_gpa_decline,
    detect_overload_risk,
    detect_prior_dn,
    detect_weak_grades,
)
from mokn.schemas.guardian import RiskFactor, RiskSeverity
from mokn.schemas.student import (
    AttendanceRecord,
    CompletedCourse,
    Student,
)


def _make_student(**overrides) -> Student:
    base = dict(
        student_id="999000001",
        name="طالب اختبار",
        major="علوم الحاسب",
        gpa=3.0,
        completed_credits=30,
        total_credits_required=132,
        courses_completed=[],
        current_courses=[],
        attendance={},
        memory_notes=[],
    )
    base.update(overrides)
    return Student.model_validate(base)


def _completed(code: str, grade: str, semester: str = "442-1", credits: int = 3) -> CompletedCourse:
    return CompletedCourse(
        code=code, name=f"اسم {code}", grade=grade, semester=semester, credits=credits
    )


# ---------------------------------------------------------------------------
# detect_attendance_risks
# ---------------------------------------------------------------------------


def test_attendance_no_factor_below_half_threshold() -> None:
    student = _make_student(attendance={"CS201": AttendanceRecord(absences=2, limit=6)})
    # 2/6 = 0.33 → below 0.5 trigger
    assert detect_attendance_risks(student) == []


def test_attendance_medium_at_half_threshold() -> None:
    student = _make_student(attendance={"CS201": AttendanceRecord(absences=3, limit=6)})
    # 3/6 = 0.50 → MEDIUM
    factors = detect_attendance_risks(student)
    assert len(factors) == 1
    assert factors[0].severity is RiskSeverity.MEDIUM
    assert factors[0].factor_type == "attendance_high"
    assert factors[0].course_code == "CS201"


def test_attendance_high_when_three_quarters() -> None:
    student = _make_student(attendance={"CS201": AttendanceRecord(absences=5, limit=6)})
    # 5/6 ≈ 0.833 → HIGH
    factors = detect_attendance_risks(student)
    assert len(factors) == 1
    assert factors[0].severity is RiskSeverity.HIGH
    assert factors[0].factor_type == "attendance_high"


def test_attendance_critical_when_at_or_over_limit() -> None:
    student = _make_student(attendance={"CS201": AttendanceRecord(absences=6, limit=6)})
    factors = detect_attendance_risks(student)
    assert len(factors) == 1
    assert factors[0].severity is RiskSeverity.CRITICAL
    assert factors[0].factor_type == "attendance_critical"
    assert factors[0].evidence["absences"] == 6
    assert factors[0].evidence["limit"] == 6


# ---------------------------------------------------------------------------
# detect_weak_grades
# ---------------------------------------------------------------------------


def test_weak_grades_none_when_all_good() -> None:
    student = _make_student(
        courses_completed=[_completed("CS101", "A"), _completed("CS102", "B+")]
    )
    assert detect_weak_grades(student) == []


def test_weak_grades_flags_C_and_D_and_F() -> None:
    student = _make_student(
        courses_completed=[
            _completed("CS101", "C"),
            _completed("CS102", "D"),
            _completed("CS103", "F"),
            _completed("CS104", "A+"),  # ignored
        ]
    )
    factors = detect_weak_grades(student)
    assert len(factors) == 3
    severities = {f.evidence["grade"]: f.severity for f in factors}
    assert severities["C"] is RiskSeverity.LOW
    assert severities["D"] is RiskSeverity.MEDIUM
    assert severities["F"] is RiskSeverity.HIGH


# ---------------------------------------------------------------------------
# detect_gpa_decline
# ---------------------------------------------------------------------------


def test_gpa_decline_none_with_only_one_semester() -> None:
    student = _make_student(
        courses_completed=[_completed("CS101", "B", semester="441-1")]
    )
    assert detect_gpa_decline(student) == []


def test_gpa_decline_flags_drop_above_threshold() -> None:
    student = _make_student(
        courses_completed=[
            _completed("CS101", "A+", semester="441-1"),  # prior term avg high
            _completed("CS102", "A", semester="441-1"),
            _completed("CS201", "C", semester="442-1"),  # current term avg low
            _completed("CS202", "D", semester="442-1"),
        ]
    )
    factors = detect_gpa_decline(student)
    assert len(factors) == 1
    assert factors[0].factor_type == "gpa_declining"
    assert factors[0].severity in {RiskSeverity.MEDIUM, RiskSeverity.HIGH}
    assert factors[0].evidence["drop"] >= 0.3


def test_gpa_decline_silent_when_drop_small() -> None:
    student = _make_student(
        courses_completed=[
            _completed("CS101", "A", semester="441-1"),
            _completed("CS201", "B+", semester="442-1"),
        ]
    )
    # Drop ~0.25 → below 0.3 threshold
    assert detect_gpa_decline(student) == []


# ---------------------------------------------------------------------------
# detect_prior_dn
# ---------------------------------------------------------------------------


def test_prior_dn_flags_arabic_phrase() -> None:
    student = _make_student(memory_notes=["غياب مرتفع — قرب الحرمان"])
    factors = detect_prior_dn(student)
    assert len(factors) == 1
    assert factors[0].factor_type == "prior_dn"
    assert factors[0].severity is RiskSeverity.HIGH


def test_prior_dn_silent_when_notes_clean() -> None:
    student = _make_student(memory_notes=["متفوق", "أداء ممتاز"])
    assert detect_prior_dn(student) == []


# ---------------------------------------------------------------------------
# detect_overload_risk
# ---------------------------------------------------------------------------


def test_overload_silent_when_target_hours_unset() -> None:
    student = _make_student(gpa=2.0)
    assert detect_overload_risk(student, target_hours=None) == []


def test_overload_silent_when_gpa_healthy() -> None:
    student = _make_student(gpa=3.5)
    assert detect_overload_risk(student, target_hours=18) == []


def test_overload_flags_low_gpa_with_heavy_load() -> None:
    student = _make_student(gpa=2.1)
    factors = detect_overload_risk(student, target_hours=18)
    assert len(factors) == 1
    assert factors[0].factor_type == "low_gpa_high_load"
    assert factors[0].evidence["target_hours"] == 18


# ---------------------------------------------------------------------------
# aggregate_severity
# ---------------------------------------------------------------------------


def _factor(sev: RiskSeverity) -> RiskFactor:
    return RiskFactor(
        factor_type="weak_grade",
        course_code=None,
        description_ar="للاختبار",
        severity=sev,
        evidence={},
    )


def test_aggregate_empty_is_low() -> None:
    assert aggregate_severity([]) is RiskSeverity.LOW


def test_aggregate_critical_dominates() -> None:
    assert (
        aggregate_severity(
            [_factor(RiskSeverity.LOW), _factor(RiskSeverity.CRITICAL)]
        )
        is RiskSeverity.CRITICAL
    )


def test_aggregate_high_then_medium_then_low() -> None:
    assert aggregate_severity([_factor(RiskSeverity.HIGH)]) is RiskSeverity.HIGH
    assert aggregate_severity([_factor(RiskSeverity.MEDIUM)]) is RiskSeverity.MEDIUM
    assert aggregate_severity([_factor(RiskSeverity.LOW)]) is RiskSeverity.LOW


# ---------------------------------------------------------------------------
# assess_student (top-level integration of detectors)
# ---------------------------------------------------------------------------


def test_assess_student_healthy_returns_low_no_factors() -> None:
    student = _make_student(
        gpa=3.9, courses_completed=[_completed("CS101", "A")]
    )
    assessment = assess_student(student)
    assert assessment.overall_severity is RiskSeverity.LOW
    assert assessment.factors == []
    assert "لا توجد" in assessment.summary_ar


def test_assess_student_at_risk_aggregates_factors() -> None:
    student = _make_student(
        gpa=2.4,
        attendance={"CS201": AttendanceRecord(absences=5, limit=6)},  # HIGH
        courses_completed=[_completed("CS101", "F")],  # HIGH
        memory_notes=["قرب الحرمان"],  # HIGH (prior_dn)
    )
    assessment = assess_student(student)
    assert assessment.overall_severity is RiskSeverity.HIGH
    assert len(assessment.factors) >= 3


def test_assess_student_passes_target_hours_to_overload() -> None:
    student = _make_student(gpa=2.1)
    assessment = assess_student(student, target_hours=18)
    types = {f.factor_type for f in assessment.factors}
    assert "low_gpa_high_load" in types


def test_assess_student_no_attendance_no_grades_does_not_crash() -> None:
    student = _make_student(courses_completed=[], attendance={}, memory_notes=[])
    assessment = assess_student(student)
    assert assessment.overall_severity is RiskSeverity.LOW
    assert assessment.factors == []


def test_assess_student_zero_limit_attendance_skipped() -> None:
    # AttendanceRecord enforces limit >= 1, but verify code-path defensively.
    with pytest.raises(Exception):
        AttendanceRecord(absences=0, limit=0)
