"""GuardianScanner — orchestrates a sweep of all students.

Flow:
  1. Pull every student from the repository.
  2. Run the deterministic risk rules (`risk_rules.assess_student`) on each.
  3. Skip students below MEDIUM severity — Guardian is not noisy.
  4. For each at-risk student, ask GuardianAgent to wrap the assessment in
     Arabic prose and a short list of recommendations.
  5. Yield events as we go so the SSE route can stream them live.

The scanner is a *thin* orchestrator: no risk logic, no Arabic strings, no
side effects beyond what the agent and repo already do.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel

from mokn.agents.guardian import GuardianAgent
from mokn.data.repository import StudentRepository
from mokn.monitoring.risk_rules import assess_student
from mokn.schemas.agent import AgentContext
from mokn.schemas.guardian import (
    GuardianRecommendation,
    ProactiveAlert,
    RiskAssessment,
    RiskSeverity,
    ScanReport,
)
from mokn.schemas.student import Student

logger = logging.getLogger(__name__)

# Severity threshold below which we suppress alerts entirely.
_ALERT_FLOOR: tuple[RiskSeverity, ...] = (
    RiskSeverity.MEDIUM,
    RiskSeverity.HIGH,
    RiskSeverity.CRITICAL,
)


class ScanStarted(BaseModel):
    kind: Literal["scan_started"] = "scan_started"
    scan_id: str
    total_students: int
    started_at: datetime


class StudentAssessed(BaseModel):
    """Lightweight progress event — emitted once per student scanned."""

    kind: Literal["student_assessed"] = "student_assessed"
    student_id: str
    severity: RiskSeverity
    factor_count: int


class AlertEvent(BaseModel):
    kind: Literal["alert"] = "alert"
    alert: ProactiveAlert


class ScanCompleted(BaseModel):
    kind: Literal["scan_completed"] = "scan_completed"
    report: ScanReport


ScanEvent = ScanStarted | StudentAssessed | AlertEvent | ScanCompleted


class GuardianScanner:
    """Drives a full or single-student proactive scan."""

    def __init__(
        self,
        repo: StudentRepository,
        agent: GuardianAgent,
    ) -> None:
        self._repo = repo
        self._agent = agent

    async def scan_all(self) -> AsyncIterator[ScanEvent]:
        """Async generator. Yields scan_started, student_assessed*, alert*,
        scan_completed in order."""
        scan_id = uuid4().hex
        started_at = datetime.now(tz=timezone.utc)
        students = await self._repo.list_all()
        yield ScanStarted(
            scan_id=scan_id,
            total_students=len(students),
            started_at=started_at,
        )

        alerts: list[ProactiveAlert] = []
        for student in students:
            assessment = assess_student(student)
            yield StudentAssessed(
                student_id=student.student_id,
                severity=assessment.overall_severity,
                factor_count=len(assessment.factors),
            )
            if assessment.overall_severity not in _ALERT_FLOOR:
                continue
            alert = await self._build_alert(student, assessment)
            if alert is None:
                continue
            alerts.append(alert)
            yield AlertEvent(alert=alert)

        completed_at = datetime.now(tz=timezone.utc)
        yield ScanCompleted(
            report=ScanReport(
                scan_id=scan_id,
                started_at=started_at,
                completed_at=completed_at,
                total_students_scanned=len(students),
                students_at_risk=len(alerts),
                alerts=alerts,
            )
        )

    async def scan_one(self, student_id: str) -> ProactiveAlert | None:
        """Single-student scan. Returns None if the student is healthy
        (severity LOW)."""
        student = await self._repo.get(student_id)
        assessment = assess_student(student)
        if assessment.overall_severity not in _ALERT_FLOOR:
            return None
        return await self._build_alert(student, assessment)

    async def run_full_report(self) -> ScanReport:
        """Convenience wrapper for callers that want the final report only."""
        report: ScanReport | None = None
        async for event in self.scan_all():
            if isinstance(event, ScanCompleted):
                report = event.report
        if report is None:
            raise RuntimeError("scan_all did not produce a ScanCompleted event")
        return report

    async def _build_alert(
        self, student: Student, assessment: RiskAssessment
    ) -> ProactiveAlert | None:
        try:
            response = await self._agent.process(
                AgentContext(
                    query="فحص استباقي لحالة الطالب",
                    student_id=student.student_id,
                    metadata={"assessment": assessment},
                )
            )
        except Exception:
            logger.exception(
                "GuardianScanner: failed to build alert for %s", student.student_id
            )
            return None

        message_ar = response.content.get("message_ar", assessment.summary_ar)
        raw_recs = response.content.get("recommendations", [])
        recommendations = [
            GuardianRecommendation.model_validate(r) for r in raw_recs
        ]
        return ProactiveAlert(
            alert_id=uuid4().hex,
            student_id=student.student_id,
            student_name=student.name,
            assessment=assessment,
            recommendations=recommendations,
            message_ar=message_ar,
        )


__all__ = [
    "AlertEvent",
    "GuardianScanner",
    "ScanCompleted",
    "ScanEvent",
    "ScanStarted",
    "StudentAssessed",
]
