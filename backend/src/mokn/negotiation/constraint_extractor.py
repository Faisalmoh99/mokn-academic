"""Turn free-form Legis veto reasons into structured HardConstraints.

The negotiation loop's biggest failure mode is Planner ignoring Legis: it
re-proposes the same schedule because the objections are just text in a
prompt. This module distills those objections into rules the deterministic
solver actually obeys (min/max credits, must-include / must-exclude codes).

The LLM produces structured output via a narrow Pydantic schema so we never
have to parse Arabic free-text by regex.
"""
from __future__ import annotations

import logging
from textwrap import dedent

from pydantic import BaseModel, Field

from mokn.llm.gemini import GeminiClient, GeminiError
from mokn.planning.optimizer import HardConstraints

logger = logging.getLogger(__name__)


class _ExtractedConstraints(BaseModel):
    min_credits: int | None = Field(default=None, ge=0, le=30)
    max_credits: int | None = Field(default=None, ge=0, le=30)
    excluded_courses: list[str] = Field(default_factory=list)
    required_courses: list[str] = Field(default_factory=list)
    rationale: str = ""


_EXTRACTOR_SYSTEM = dedent(
    """
    أنت محلل دقيق يستخرج قيوداً رقمية من اعتراضات وكيل اللوائح.
    لا تخمن. إن لم يُذكر قيد فاتركه null أو فارغاً.
    """
).strip()


def _build_prompt(objections: list[str]) -> str:
    if not objections:
        return ""
    joined = "\n".join(f"- {o}" for o in objections)
    return dedent(
        f"""
        الاعتراضات التي رفعها وكيل اللوائح:
        {joined}

        استخرج المخرجات التالية بصيغة JSON مطابقة لـ _ExtractedConstraints:
        - min_credits: الحد الأدنى الإجباري للساعات (إن ذُكر صراحةً، مثل "الحد الأدنى 12 ساعة").
        - max_credits: الحد الأقصى المسموح للساعات (إن ذُكر صراحةً، مثل "بحد أقصى 15 ساعة").
        - excluded_courses: أكواد المواد التي يجب استبعادها (مثل CS302).
        - required_courses: أكواد المواد التي يجب تضمينها.
        - rationale: جملة قصيرة بالعربية تشرح القيود التي استخرجتها.

        إذا لم يُذكر قيد معيّن في الاعتراضات، اتركه null أو [].
        """
    ).strip()


async def extract_constraints_from_objections(
    objections: list[str],
    llm: GeminiClient,
) -> HardConstraints:
    """Distill prior Legis objections into HardConstraints the solver obeys.

    Returns an empty HardConstraints when there are no objections, the LLM
    can't extract anything, or the call fails — the caller should treat that
    as "no new constraints; behave as round 1."
    """
    if not objections:
        return HardConstraints()

    try:
        extracted: _ExtractedConstraints = await llm.generate(
            _build_prompt(objections),
            system=_EXTRACTOR_SYSTEM,
            temperature=0.0,
            response_schema=_ExtractedConstraints,
        )
    except GeminiError:
        logger.warning("constraint extraction failed; proceeding with empty constraints")
        return HardConstraints()

    if extracted.min_credits and extracted.max_credits:
        if extracted.min_credits > extracted.max_credits:
            # The regulator can't simultaneously demand "at least X" and "at
            # most Y < X" — drop the contradictory pair so the solver still
            # returns something. Logged so we can audit if it recurs.
            logger.warning(
                "constraint extractor produced inverted bounds: min=%s > max=%s",
                extracted.min_credits,
                extracted.max_credits,
            )
            return HardConstraints()

    return HardConstraints(
        min_credits=extracted.min_credits,
        max_credits=extracted.max_credits,
        excluded_courses=set(extracted.excluded_courses),
        required_courses=set(extracted.required_courses),
    )
