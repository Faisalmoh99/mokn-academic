"""Run each demo scenario end-to-end and save the NegotiationSession as JSON.

Produces the canned transcripts the dashboard replays in Offline Mode so the
live demo still works when Gemini 503s or the venue Wi-Fi dies. Each run hits
the real LangGraph — Gemini, Chroma, and all.

Run:
    python scripts/capture_demo_sessions.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from mokn.agents.legis import get_legis_agent  # noqa: E402
from mokn.agents.orchestrator import get_orchestrator_agent  # noqa: E402
from mokn.agents.planner import get_planner_agent  # noqa: E402
from mokn.config import configure_logging, get_settings  # noqa: E402
from mokn.data.repository import (  # noqa: E402
    get_course_repository,
    get_student_repository,
)
from mokn.negotiation.constraint_extractor import (  # noqa: E402
    extract_constraints_from_objections,
)
from mokn.negotiation.graph import run_negotiation  # noqa: E402
from mokn.planning.optimizer import HardConstraints  # noqa: E402

SCENARIOS = [
    {
        "file": "01_regulation_question.json",
        "student_id": None,
        "request": "كم الحد الأقصى للساعات لطالب معدله 3.5؟",
        "description": "سؤال عن اللوائح — Legis يجيب مباشرة",
    },
    {
        "file": "02_happy_schedule.json",
        "student_id": "442001234",
        "request": "ابني لي جدول 12 ساعة",
        "description": "طالب ممتاز GPA 3.2 — جولة واحدة",
    },
    {
        "file": "03_real_negotiation.json",
        "student_id": "442005678",
        "request": "ابني لي جدول 21 ساعة",
        "description": "تفاوض حقيقي — Legis يعترض، Planner يعدل",
    },
    {
        "file": "04_at_risk_student.json",
        "student_id": "442009876",
        "request": "ابني لي جدول 15 ساعة",
        "description": "طالب عنده غياب عالي — warnings واضحة",
    },
]


async def main() -> int:
    settings = get_settings()
    configure_logging(settings)

    output_dir = Path(__file__).resolve().parents[1] / "data" / "demo_sessions"
    output_dir.mkdir(parents=True, exist_ok=True)

    orchestrator = get_orchestrator_agent()
    planner = get_planner_agent()
    legis = get_legis_agent()
    students = get_student_repository()
    courses = get_course_repository()

    async def _extract(objections: list[str]) -> HardConstraints:
        return await extract_constraints_from_objections(objections, orchestrator._llm)

    for scenario in SCENARIOS:
        print(f"\n→ {scenario['description']}")
        print(f"  request: {scenario['request']}")
        t0 = time.monotonic()
        session = await run_negotiation(
            user_request=scenario["request"],
            student_id=scenario["student_id"],
            orchestrator=orchestrator,
            planner=planner,
            legis=legis,
            students=students,
            courses=courses,
            max_rounds=3,
            constraints_extractor=_extract,
        )
        elapsed = time.monotonic() - t0

        path = output_dir / scenario["file"]
        path.write_text(
            json.dumps(
                session.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(
            f"  ✓ saved {path.name} — {len(session.turns)} turns, "
            f"outcome={session.outcome.value if session.outcome else 'none'}, "
            f"{elapsed:.1f}s"
        )

    print("\n✓ All scenarios captured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
