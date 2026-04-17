"""Schemas for Legis / regulations knowledge."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["high", "medium", "low"]


class RegulationCitation(BaseModel):
    """A single cited passage from the regulations corpus."""

    text: str = Field(..., description="The verbatim passage supporting the claim.")
    source: str = Field(..., description="Source document filename or identifier.")
    page: int = Field(..., ge=0, description="Page number in the source document.")
    section: str | None = Field(
        default=None, description="Section heading, if extractable."
    )


class RegulationAnswer(BaseModel):
    """Structured answer from Legis to a regulation question."""

    answer: str = Field(..., description="Concise Arabic answer to the question.")
    citations: list[RegulationCitation] = Field(
        default_factory=list,
        description="Passages Legis relied on. Empty only when answer is 'not found'.",
    )
    confidence: Confidence = Field(
        default="medium",
        description="Legis' self-rated confidence. 'low' when passages are weak.",
    )


class RetrievedChunk(BaseModel):
    """A chunk returned from the vector store for a query."""

    text: str
    source: str
    page: int
    section: str | None = None
    score: float = Field(..., description="Distance or similarity score from Chroma.")
    chunk_id: str
