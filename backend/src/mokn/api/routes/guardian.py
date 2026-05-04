"""HTTP surface for the Guardian agent.

Guardian is *outside* the negotiation loop: its routes live alongside the
others but never feed the LangGraph state machine. The SSE format mirrors
`/api/negotiate/stream` exactly so the dashboard can reuse its frame parser.
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from mokn.api.deps import GuardianDep, StudentRepoDep
from mokn.data.repository import StudentNotFound
from mokn.monitoring.scanner import (
    AlertEvent,
    GuardianScanner,
    ScanCompleted,
    ScanStarted,
    StudentAssessed,
)
from mokn.schemas.guardian import ProactiveAlert, ScanReport

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/guardian", tags=["guardian"])


@router.get("/health")
async def guardian_health() -> dict[str, str]:
    return {"status": "ok", "agent": "Guardian"}


@router.post("/assess/{student_id}", response_model=ProactiveAlert | None)
async def assess_one(
    student_id: str, guardian: GuardianDep, students: StudentRepoDep
) -> ProactiveAlert | None:
    scanner = GuardianScanner(repo=students, agent=guardian)
    try:
        return await scanner.scan_one(student_id)
    except StudentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"student not found: {student_id}",
        ) from exc


@router.post("/scan/run", response_model=ScanReport)
async def run_scan(guardian: GuardianDep, students: StudentRepoDep) -> ScanReport:
    scanner = GuardianScanner(repo=students, agent=guardian)
    return await scanner.run_full_report()


@router.get("/scan/stream")
async def stream_scan(
    guardian: GuardianDep, students: StudentRepoDep
) -> StreamingResponse:
    """Server-Sent Events: one event per scan lifecycle moment.

    Event types — matches the framing used by /api/negotiate/stream:
      - scan_started:    {scan_id, total_students, started_at}
      - student_assessed: {student_id, severity, factor_count}
      - alert:           ProactiveAlert
      - scan_completed:  ScanReport
    """
    scanner = GuardianScanner(repo=students, agent=guardian)

    async def event_generator() -> AsyncIterator[str]:
        try:
            async for event in scanner.scan_all():
                if isinstance(event, ScanStarted):
                    yield _sse_event(
                        "scan_started",
                        {
                            "scan_id": event.scan_id,
                            "total_students": event.total_students,
                            "started_at": event.started_at.isoformat(),
                        },
                    )
                elif isinstance(event, StudentAssessed):
                    yield _sse_event(
                        "student_assessed",
                        {
                            "student_id": event.student_id,
                            "severity": event.severity.value,
                            "factor_count": event.factor_count,
                        },
                    )
                elif isinstance(event, AlertEvent):
                    yield _sse_event("alert", event.alert.model_dump(mode="json"))
                elif isinstance(event, ScanCompleted):
                    yield _sse_event(
                        "scan_completed", event.report.model_dump(mode="json")
                    )
        except Exception as exc:  # noqa: BLE001 — surface failure to the client
            logger.exception("guardian scan stream failed: %s", exc)
            yield _sse_event("error", {"message": str(exc)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"
