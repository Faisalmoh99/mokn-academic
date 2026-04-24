"""HTTP surface for the Legis agent."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from mokn.api.deps import LegisDep
from mokn.schemas.agent import AgentContext, VetoDecision
from mokn.schemas.regulations import RegulationAnswer

router = APIRouter(prefix="/api/legis", tags=["legis"])


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Arabic regulation question.")
    student_id: str | None = Field(default=None)


class ValidateRequest(BaseModel):
    proposal: dict[str, Any] = Field(
        ..., description="Proposal JSON to review — usually a schedule shape."
    )
    context: dict[str, Any] = Field(default_factory=dict)


@router.post("/ask", response_model=RegulationAnswer)
async def ask_legis(payload: AskRequest, legis: LegisDep) -> RegulationAnswer:
    ctx = AgentContext(query=payload.question, student_id=payload.student_id)
    response = await legis.process(ctx)
    try:
        return RegulationAnswer.model_validate(response.content)
    except Exception as exc:  # pragma: no cover — defensive
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Legis returned unparseable content: {exc}",
        ) from exc


@router.post("/validate-proposal", response_model=VetoDecision | None)
async def validate_proposal(
    payload: ValidateRequest, legis: LegisDep
) -> VetoDecision | None:
    return await legis.can_veto(payload.proposal)
