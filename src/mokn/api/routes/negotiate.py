"""HTTP surface for the Orchestrator-driven negotiation loop.

`POST /api/negotiate` is the real entrypoint — replaces the precursor
`/api/planner/validate-with-legis` from Session 2. The rest are read-only
endpoints the dashboard (Session 5) will hit to render past sessions.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
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
from mokn.negotiation.graph import run_negotiation
from mokn.planning.optimizer import HardConstraints
from mokn.schemas.negotiation import NegotiationSession, NegotiationTurn

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
