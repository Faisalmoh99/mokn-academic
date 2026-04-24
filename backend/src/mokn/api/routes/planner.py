"""HTTP surface for the Planner agent + Planner↔Legis precursor loop.

`/api/planner/validate-with-legis` is deliberately a single round-trip — not
a full negotiation — so Session 3 can replace it with the real LangGraph
orchestration while the rest of the stack stays unchanged.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from mokn.api.deps import LegisDep, PlannerDep
from mokn.data.repository import StudentNotFound
from mokn.schemas.agent import AgentContext, VetoDecision
from mokn.schemas.schedule import ScheduleProposal

router = APIRouter(prefix="/api/planner", tags=["planner"])


class BuildScheduleRequest(BaseModel):
    student_id: str = Field(..., min_length=1)
    target_hours: int = Field(..., ge=3, le=24)
    target_semester: str = Field(..., description="e.g., 'fall-2026' or 'spring'.")


class ValidateRequest(BaseModel):
    student_id: str = Field(..., min_length=1)
    proposal: ScheduleProposal


class ValidatedProposal(BaseModel):
    proposal: ScheduleProposal
    legis_veto: VetoDecision | None = None


@router.post("/build-schedule", response_model=ScheduleProposal)
async def build_schedule(payload: BuildScheduleRequest, planner: PlannerDep) -> ScheduleProposal:
    ctx = AgentContext(
        query=f"اقترح جدولاً للطالب {payload.student_id} في {payload.target_semester}",
        student_id=payload.student_id,
        metadata={
            "target_hours": payload.target_hours,
            "target_semester": payload.target_semester,
        },
    )
    try:
        response = await planner.process(ctx)
    except StudentNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"student not found: {exc}",
        ) from exc
    return ScheduleProposal.model_validate(response.content)


@router.post("/validate-with-legis", response_model=ValidatedProposal, deprecated=True)
async def validate_with_legis(
    payload: ValidateRequest, legis: LegisDep
) -> ValidatedProposal:
    """DEPRECATED: use /api/negotiate instead.

    Single-round Planner→Legis handoff from Session 2. Kept so existing tests
    and clients still work, but the real negotiation loop now lives in
    `/api/negotiate` — which runs the Orchestrator + cyclic graph.
    """
    recommended = next(
        (o for o in payload.proposal.options if o.label == payload.proposal.recommended_option),
        payload.proposal.options[0],
    )

    legis_input: dict[str, Any] = {
        "type": "schedule",
        "student": {"id": payload.student_id},
        "courses": [
            {"code": c.course_code, "credits": c.credits} for c in recommended.courses
        ],
        "total_credits": recommended.total_credits,
    }
    veto = await legis.can_veto(legis_input)
    return ValidatedProposal(proposal=payload.proposal, legis_veto=veto)
