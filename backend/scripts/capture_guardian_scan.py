"""Capture a deterministic Guardian scan for offline demo replay.

Runs the real risk-rules layer over the seeded students.json, then wraps
each at-risk assessment with hand-written Arabic prose (no live LLM call).
This keeps the dashboard demo reproducible without needing the API up.

Run:
    python -m scripts.capture_guardian_scan
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

# Ensure src is importable when run directly.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("GEMINI_API_KEY", "offline-capture")

from mokn.agents.guardian import GuardianAgent  # noqa: E402
from mokn.data.repository import StudentRepository  # noqa: E402
from mokn.monitoring.scanner import GuardianScanner  # noqa: E402
from mokn.schemas.agent import AgentContext, AgentResponse  # noqa: E402
from mokn.schemas.guardian import (  # noqa: E402
    GuardianRecommendation,
    RiskAssessment,
    RiskSeverity,
)


def _hand_written_prose(assessment: RiskAssessment) -> tuple[str, list[GuardianRecommendation]]:
    """Deterministic Arabic prose keyed off the assessment.

    Mirrors the kind of message Gemini would produce, without the variance.
    """
    first_name = assessment.student_name.split()[0] if assessment.student_name else "الطالب"
    severity = assessment.overall_severity
    factor_types = {f.factor_type for f in assessment.factors}

    # Build a short message tied to the strongest factor.
    parts = [f"مرحباً {first_name}،"]
    if "attendance_critical" in factor_types or severity is RiskSeverity.CRITICAL:
        parts.append(
            "رصدنا غياباً وصل أو تجاوز الحد المسموح به في إحدى موادك. "
            "هذا يستوجب تدخّلاً سريعاً قبل صدور قرار الحرمان."
        )
    elif "attendance_high" in factor_types:
        parts.append(
            "نسبة غيابك في إحدى المواد تقترب من الحد المسموح به. "
            "بإمكانك تعديل المسار قبل أن يتفاقم الوضع."
        )
    elif "gpa_declining" in factor_types:
        parts.append(
            "لاحظنا انخفاضاً في معدلك الفصلي مقارنة بالفصل السابق. "
            "ربما يستحق الأمر مراجعة سريعة لتفادي تراكم التعثّر."
        )
    elif "weak_grade" in factor_types:
        parts.append(
            "هناك تقديرات منخفضة في عدد من المواد قد تؤثر على معدلك التراكمي."
        )
    elif "prior_dn" in factor_types:
        parts.append(
            "يوجد سجل سابق متعلق بقرب الحرمان — ننصح بمتابعة دقيقة هذا الفصل."
        )
    else:
        parts.append("هناك مؤشرات بسيطة تستحق الانتباه قبل أن تتراكم.")

    parts.append(
        "إن أحببت تفاصيل أكثر أو خيارات أوضح، تواصل مع مرشدك الأكاديمي البشري."
    )
    message = " ".join(parts)

    recs: list[GuardianRecommendation] = []
    if "attendance_critical" in factor_types:
        recs.append(
            GuardianRecommendation(
                title_ar="مراجعة فورية للمرشد",
                rationale_ar="الغياب تجاوز الحد — قد يكون قرار الحرمان وشيكاً.",
                suggested_action="consult_advisor",
                priority="urgent",
            )
        )
        recs.append(
            GuardianRecommendation(
                title_ar="تحسين الحضور",
                rationale_ar="الالتزام في الأسابيع المتبقية يمنع تكرار الموقف لاحقاً.",
                suggested_action="improve_attendance",
                priority="urgent",
            )
        )
    elif "attendance_high" in factor_types:
        recs.append(
            GuardianRecommendation(
                title_ar="تحسين الحضور",
                rationale_ar="نسبة الغياب تقترب من الحد — تجنّب أي غياب إضافي.",
                suggested_action="improve_attendance",
                priority="advisory",
            )
        )
    if "gpa_declining" in factor_types:
        recs.append(
            GuardianRecommendation(
                title_ar="مراجعة الخطة الدراسية",
                rationale_ar="انخفاض المعدل الفصلي قد يكون مؤشراً على عبء غير مناسب.",
                suggested_action="review_study_plan",
                priority="advisory",
            )
        )
    if "weak_grade" in factor_types and "attendance_critical" not in factor_types:
        recs.append(
            GuardianRecommendation(
                title_ar="استشارة المرشد بشأن المواد المتعثّر فيها",
                rationale_ar="تكرار التقديرات المنخفضة يستدعي خطة دعم.",
                suggested_action="consult_advisor",
                priority="advisory",
            )
        )
    if not recs:
        recs.append(
            GuardianRecommendation(
                title_ar="مراجعة دورية مع المرشد",
                rationale_ar="لتأكيد سلامة المسار الأكاديمي وتفادي المفاجآت.",
                suggested_action="consult_advisor",
                priority="info",
            )
        )
    return message, recs


class _StubGuardian(GuardianAgent):
    """Replaces the LLM call with hand-written Arabic prose."""

    def __init__(self) -> None:  # bypass parent __init__
        pass

    async def process(self, context: AgentContext) -> AgentResponse:  # type: ignore[override]
        assessment = context.metadata["assessment"]
        message, recs = _hand_written_prose(assessment)
        return AgentResponse(
            agent="Guardian",
            content={
                "message_ar": message,
                "recommendations": [r.model_dump() for r in recs],
                "assessment": assessment.model_dump(),
            },
            reasoning="offline-capture",
            confidence="high",
        )


async def main() -> None:
    repo = StudentRepository(ROOT / "data" / "mock" / "students.json")
    scanner = GuardianScanner(repo=repo, agent=_StubGuardian())

    # Use deterministic timestamps so the captured JSON is byte-stable.
    started_at = datetime(2026, 5, 4, 9, 0, 0, tzinfo=timezone.utc)
    completed_at = datetime(2026, 5, 4, 9, 0, 12, tzinfo=timezone.utc)

    students = await repo.list_all()
    alerts = []
    for student in students:
        alert = await scanner.scan_one(student.student_id)
        if alert is None:
            continue
        # Stamp deterministic ids/timestamps for replay stability.
        alert.alert_id = uuid4().hex  # still random; OK for demo
        alert.triggered_at = started_at
        alerts.append(alert)

    # Sort highest severity first so the demo reads like a triage feed.
    severity_order = {
        RiskSeverity.CRITICAL: 0,
        RiskSeverity.HIGH: 1,
        RiskSeverity.MEDIUM: 2,
        RiskSeverity.LOW: 3,
    }
    alerts.sort(key=lambda a: severity_order[a.assessment.overall_severity])

    report = {
        "scan_id": "offline-demo-001",
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "total_students_scanned": len(students),
        "students_at_risk": len(alerts),
        "alerts": [json.loads(a.model_dump_json()) for a in alerts],
    }

    out_path = ROOT.parent / "dashboard" / "public" / "demo_sessions" / "guardian_proactive_scan.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {out_path}")
    print(
        f"  scanned={len(students)} at_risk={len(alerts)} "
        + " ".join(
            f"{a.student_name}={a.assessment.overall_severity.value}" for a in alerts
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
