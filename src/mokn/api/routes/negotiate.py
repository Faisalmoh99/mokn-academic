"""HTTP surface for the Orchestrator-driven negotiation loop.

`POST /api/negotiate` is the real entrypoint — replaces the precursor
`/api/planner/validate-with-legis` from Session 2. `/api/negotiate/stream`
is the Session 4 addition: Server-Sent Events so the dashboard can animate
each turn as it fires instead of waiting 20-40 seconds for a batch reply.
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from mokn.api.deps import (
    CourseRepoDep,
    LegisDep,
    NegotiationStoreDep,
    OrchestratorDep,
    PlannerDep,
    StudentRepoDep,
)
from mokn.negotiation.constraint_extractor import extract_constraints_from_objections
from mokn.negotiation.graph import run_negotiation, run_negotiation_stream
from mokn.planning.optimizer import HardConstraints
from mokn.schemas.negotiation import NegotiationSession, NegotiationTurn

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/negotiate", tags=["negotiate"])


class NegotiateRequest(BaseModel):
    student_id: str | None = Field(
        default=None,
        description="Optional — required for schedule requests, ignored for regulation questions.",
    )
    request: str = Field(..., min_length=1, description="Free-text Arabic student message.")
    max_rounds: int = Field(default=3, ge=1, le=6)


class SessionList(BaseModel):
    sessions: list[NegotiationSession]


class ReplayResponse(BaseModel):
    session_id: str
    turns: list[NegotiationTurn]


@router.post("", response_model=NegotiationSession)
async def negotiate(
    payload: NegotiateRequest,
    orchestrator: OrchestratorDep,
    planner: PlannerDep,
    legis: LegisDep,
    students: StudentRepoDep,
    courses: CourseRepoDep,
    store: NegotiationStoreDep,
) -> NegotiationSession:
    async def _extract(objections: list[str]) -> HardConstraints:
        return await extract_constraints_from_objections(objections, orchestrator._llm)

    session = await run_negotiation(
        user_request=payload.request,
        student_id=payload.student_id,
        orchestrator=orchestrator,
        planner=planner,
        legis=legis,
        students=students,
        courses=courses,
        max_rounds=payload.max_rounds,
        constraints_extractor=_extract,
    )
    await store.save(session)
    return session


@router.post("/stream")
async def negotiate_stream(
    payload: NegotiateRequest,
    orchestrator: OrchestratorDep,
    planner: PlannerDep,
    legis: LegisDep,
    students: StudentRepoDep,
    courses: CourseRepoDep,
    store: NegotiationStoreDep,
) -> StreamingResponse:
    """Server-Sent Events stream. One `turn` event per NegotiationTurn as the
    LangGraph progresses, bookended by `session_start` and `done` (or `error`).
    """

    async def _extract(objections: list[str]) -> HardConstraints:
        return await extract_constraints_from_objections(objections, orchestrator._llm)

    session_id = uuid4().hex

    async def event_generator() -> AsyncIterator[str]:
        yield _sse_event(
            "session_start",
            {
                "session_id": session_id,
                "request": payload.request,
                "student_id": payload.student_id,
            },
        )
        try:
            final_session: NegotiationSession | None = None
            async for kind, value in run_negotiation_stream(
                user_request=payload.request,
                student_id=payload.student_id,
                orchestrator=orchestrator,
                planner=planner,
                legis=legis,
                students=students,
                courses=courses,
                max_rounds=payload.max_rounds,
                session_id=session_id,
                constraints_extractor=_extract,
            ):
                if kind == "turn":
                    yield _sse_event("turn", value.model_dump(mode="json"))
                elif kind == "session":
                    final_session = value

            if final_session is not None:
                await store.save(final_session)
                yield _sse_event("done", final_session.model_dump(mode="json"))
            else:
                yield _sse_event(
                    "error",
                    {"message": "negotiation finished without producing a session"},
                )
        except Exception as exc:  # noqa: BLE001 — surface any failure to the client
            logger.exception("negotiate_stream failed: %s", exc)
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


@router.get("/sessions", response_model=SessionList)
async def list_sessions(store: NegotiationStoreDep, limit: int = 20) -> SessionList:
    if limit < 1 or limit > 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="limit must be between 1 and 200",
        )
    sessions = await store.list_recent(limit=limit)
    return SessionList(sessions=sessions)


@router.get("/sessions/{session_id}", response_model=NegotiationSession)
async def get_session(session_id: str, store: NegotiationStoreDep) -> NegotiationSession:
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"session not found: {session_id}",
        )
    return session


@router.post("/sessions/{session_id}/replay", response_model=ReplayResponse)
async def replay_session(
    session_id: str, store: NegotiationStoreDep
) -> ReplayResponse:
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"session not found: {session_id}",
        )
    return ReplayResponse(session_id=session.session_id, turns=session.turns)
