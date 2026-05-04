"""Guardian agent schemas — proactive risk monitoring layer.

Guardian runs *outside* the negotiation loop. It scans student records on a
cadence (a button press in the demo, a real cron in production), produces
deterministic RiskAssessments, and asks the LLM to wrap them in warm Arabic
prose. These schemas are the contract between the rules layer
(`mokn.monitoring.risk_rules`), the agent (`mokn.agents.guardian`), the
scanner (`mokn.monitoring.scanner`), and the HTTP routes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class RiskSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


RiskFactorType = Literal[
    "attendance_high",
    "attendance_critical",
    "weak_grade",
    "gpa_declining",
    "prior_dn",
    "low_gpa_high_load",
]


class RiskFactor(BaseModel):
    """A single concerning data point about a student.

    Always emitted by a deterministic detector — never inferred by the LLM.
    `evidence` carries the raw numbers behind the flag so the dashboard can
    show "why" without re-deriving anything.
    """

    factor_type: RiskFactorType
    course_code: str | None = Field(
        default=None,
        description="The course this factor relates to; null for student-wide factors.",
    )
    description_ar: str
    severity: RiskSeverity
    evidence: dict[str, Any] = Field(default_factory=dict)


class RiskAssessment(BaseModel):
    """Aggregate assessment for one student at a single point in time."""

    student_id: str
    student_name: str
    overall_severity: RiskSeverity
    factors: list[RiskFactor] = Field(default_factory=list)
    summary_ar: str


GuardianRecommendationAction = Literal[
    "reduce_credit_hours",
    "drop_at_risk_course",
    "consult_advisor",
    "improve_attendance",
    "review_study_plan",
]
GuardianRecommendationPriority = Literal["info", "advisory", "urgent"]


class GuardianRecommendation(BaseModel):
    """Concrete suggestion. Guardian suggests; it never forces."""

    title_ar: str
    rationale_ar: str
    suggested_action: GuardianRecommendationAction
    priority: GuardianRecommendationPriority


class ProactiveAlert(BaseModel):
    """The full alert surfaced to a single student."""

    alert_id: str
    student_id: str
    student_name: str
    triggered_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )
    assessment: RiskAssessment
    recommendations: list[GuardianRecommendation] = Field(default_factory=list)
    message_ar: str


class ScanReport(BaseModel):
    """Result of scanning all students."""

    scan_id: str
    started_at: datetime
    completed_at: datetime
    total_students_scanned: int
    students_at_risk: int
    alerts: list[ProactiveAlert] = Field(default_factory=list)


__all__ = [
    "GuardianRecommendation",
    "GuardianRecommendationAction",
    "GuardianRecommendationPriority",
    "ProactiveAlert",
    "RiskAssessment",
    "RiskFactor",
    "RiskFactorType",
    "RiskSeverity",
    "ScanReport",
]
