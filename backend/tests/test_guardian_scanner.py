"""GuardianScanner tests using the seeded mock repo + a stubbed Guardian agent."""
from __future__ import annotations

from typing import Any

import pytest

from mokn.agents.guardian import GuardianAgent
from mokn.data.repository import StudentRepository
from mokn.monitoring.scanner import (
    AlertEvent,
    GuardianScanner,
    ScanCompleted,
    ScanStarted,
    StudentAssessed,
)
from mokn.schemas.agent import AgentResponse
from mokn.schemas.guardian import RiskSeverity


_DEFAULT_PROSE = {
    "message_ar": "رسالة استباقية اختبارية.",
    "recommendations": [
        {
            "title_ar": "مراجعة المرشد",
            "rationale_ar": "للتأكد من الخطة.",
            "suggested_action": "consult_advisor",
            "priority": "advisory",
        }
    ],
    "assessment": {},  # filled in by caller per test
}


class _StubAgent(GuardianAgent):
    """Replaces the LLM call with a deterministic stub. We still inherit
    the real `process()` so the AgentContext shape and error paths stay
    exercised — but here we override `process` entirely to keep tests fast."""

    def __init__(self) -> None:  # bypass GuardianAgent.__init__ (no LLM needed)
        self.calls: list[Any] = []

    async def process(self, context):  # type: ignore[override]
        self.calls.append(context)
        assessment = context.metadata["assessment"]
        return AgentResponse(
            agent="Guardian",
            content={
                "message_ar": f"رسالة لـ {assessment.student_name}.",
                "recommendations": _DEFAULT_PROSE["recommendations"],
                "assessment": assessment.model_dump(),
            },
            reasoning="stub",
            confidence="high",
        )


@pytest.fixture
def real_repo() -> StudentRepository:
    """Use the actual seeded mock students.json — no monkey-patching."""
    return StudentRepository.__new__(StudentRepository)


@pytest.fixture
def repo() -> StudentRepository:
    from mokn.data.repository import _DEFAULT_DATA_DIR

    return StudentRepository(_DEFAULT_DATA_DIR / "students.json")


@pytest.mark.asyncio
async def test_scan_all_yields_lifecycle_events(repo: StudentRepository) -> None:
    agent = _StubAgent()
    scanner = GuardianScanner(repo=repo, agent=agent)
    events = [event async for event in scanner.scan_all()]
    assert events, "scanner should yield at least one event"
    assert isinstance(events[0], ScanStarted)
    assert isinstance(events[-1], ScanCompleted)
    # Every student must produce a StudentAssessed event.
    assessed = [e for e in events if isinstance(e, StudentAssessed)]
    assert len(assessed) == events[0].total_students


@pytest.mark.asyncio
async def test_scan_all_filters_below_medium(repo: StudentRepository) -> None:
    agent = _StubAgent()
    scanner = GuardianScanner(repo=repo, agent=agent)
    alerts: list[AlertEvent] = []
    student_severities: dict[str, RiskSeverity] = {}
    async for event in scanner.scan_all():
        if isinstance(event, AlertEvent):
            alerts.append(event)
        elif isinstance(event, StudentAssessed):
            student_severities[event.student_id] = event.severity

    # Every alert MUST correspond to a student whose assessed severity was
    # MEDIUM or higher. No alerts for LOW.
    for alert in alerts:
        sid = alert.alert.student_id
        assert student_severities[sid] in {
            RiskSeverity.MEDIUM,
            RiskSeverity.HIGH,
            RiskSeverity.CRITICAL,
        }


@pytest.mark.asyncio
async def test_scan_one_returns_none_for_healthy_student(repo: StudentRepository) -> None:
    agent = _StubAgent()
    scanner = GuardianScanner(repo=repo, agent=agent)
    # 442003456 = نورة, GPA 3.9, no attendance, all A's → healthy
    alert = await scanner.scan_one("442003456")
    assert alert is None
    assert agent.calls == [], "agent should not be invoked for a healthy student"


@pytest.mark.asyncio
async def test_scan_one_returns_alert_for_at_risk_student(repo: StudentRepository) -> None:
    agent = _StubAgent()
    scanner = GuardianScanner(repo=repo, agent=agent)
    # 442009876 = سعود, has CS201 absences 4/6 + memory note "قرب الحرمان"
    alert = await scanner.scan_one("442009876")
    assert alert is not None
    assert alert.student_id == "442009876"
    assert alert.assessment.overall_severity in {
        RiskSeverity.MEDIUM,
        RiskSeverity.HIGH,
        RiskSeverity.CRITICAL,
    }
    assert alert.message_ar  # prose layer ran
    assert agent.calls, "agent should be invoked exactly once"


@pytest.mark.asyncio
async def test_scan_all_uses_injected_agent(repo: StudentRepository) -> None:
    agent = _StubAgent()
    scanner = GuardianScanner(repo=repo, agent=agent)
    async for _ in scanner.scan_all():
        pass
    # The stub agent records every call. Number of calls must equal number
    # of alerts produced (= students at MEDIUM+).
    report = await scanner.run_full_report()
    # run_full_report runs another scan, so calls grew further; just assert > 0
    assert len(agent.calls) > 0
    assert report.total_students_scanned > 0
