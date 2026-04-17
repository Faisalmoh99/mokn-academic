"""Legis — the regulations guardian.

Legis answers regulation questions from a RAG corpus (never from the LLM's
prior knowledge) and holds veto power over proposals that break the rules.
For Session 1, veto covers schedule-shaped proposals; other proposal types
are handled by other agents in later sessions.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from textwrap import dedent
from typing import Any

from mokn.agents.base import BaseAgent
from mokn.llm.gemini import GeminiClient, get_gemini_client
from mokn.memory.knowledge import KnowledgeBase, get_knowledge_base
from mokn.schemas.agent import AgentContext, AgentResponse, VetoDecision
from mokn.schemas.regulations import RegulationAnswer, RegulationCitation, RetrievedChunk

logger = logging.getLogger(__name__)

LEGIS_SYSTEM_PROMPT = dedent(
    """
    أنت "Legis" — الوكيل المتخصص في لوائح جامعة الأمير سطام بن عبدالعزيز.
    دورك: الإجابة على أسئلة اللوائح بدقة، مع الاستشهاد بالمصدر.
    قواعد صارمة:
    1. لا تجب من معرفتك العامة. أجب فقط من المقاطع المرفقة.
    2. كل ادعاء يجب أن يكون مصحوباً برقم المقطع الذي استند إليه.
    3. إذا لم تجد إجابة في المقاطع، قل "لا أجد هذا في اللوائح المتاحة".
    4. أجب بالعربية الفصحى المبسطة.
    """
).strip()

VETO_SYSTEM_PROMPT = dedent(
    """
    أنت "Legis" في وضع المراجعة. تفحص اقتراحاً من وكيل آخر (غالباً Planner)
    مقابل مقاطع اللوائح المرفقة. قواعد:
    1. ارفض (veto=true) فقط عند وجود مخالفة صريحة مدعومة بالمقاطع.
    2. إذا كانت المقاطع لا تغطي السؤال، اعتبره مقبولاً (veto=false) مع سبب موجز.
    3. اذكر القواعد المخالفة بأسماء مختصرة.
    4. عند الرفض، اقترح بديلاً إن أمكن.
    5. أجب بالعربية.
    """
).strip()

# Confidence heuristic: cosine distances under this are "good" matches.
_STRONG_MATCH_DISTANCE = 0.35
_WEAK_MATCH_DISTANCE = 0.65


class LegisAgent(BaseAgent):
    """Regulations agent: cited answers + rule-based veto."""

    def __init__(
        self,
        knowledge: KnowledgeBase | None = None,
        llm: GeminiClient | None = None,
        top_k: int = 5,
    ) -> None:
        self._knowledge = knowledge or get_knowledge_base("regulations")
        self._llm = llm or get_gemini_client()
        self._top_k = top_k

    @property
    def name(self) -> str:
        return "Legis"

    @property
    def role_description(self) -> str:
        return "حارس اللوائح الأكاديمية للجامعة"

    @property
    def system_prompt(self) -> str:
        return LEGIS_SYSTEM_PROMPT

    async def process(self, context: AgentContext) -> AgentResponse:
        passages = await self._knowledge.query(context.query, top_k=self._top_k)

        if not passages:
            answer = RegulationAnswer(
                answer="لا أجد هذا في اللوائح المتاحة.",
                citations=[],
                confidence="low",
            )
            return self._wrap(answer, reasoning="no passages returned from KB")

        prompt = _build_answer_prompt(context.query, passages)
        raw: RegulationAnswer = await self._llm.generate(
            prompt,
            system=self.system_prompt,
            temperature=0.2,
            response_schema=RegulationAnswer,
        )
        grounded = _enforce_citations(raw, passages)
        grounded.confidence = _score_confidence(passages)
        return self._wrap(grounded, reasoning=f"retrieved {len(passages)} passages")

    async def can_veto(self, proposal: dict[str, Any]) -> VetoDecision | None:
        """Veto schedule proposals that violate cited regulations."""
        if not _looks_like_schedule(proposal):
            return None

        query = _schedule_probe_query(proposal)
        passages = await self._knowledge.query(query, top_k=self._top_k)
        if not passages:
            logger.debug("Legis.can_veto: no regulation context; abstaining")
            return None

        prompt = _build_veto_prompt(proposal, passages)
        decision: VetoDecision = await self._llm.generate(
            prompt,
            system=VETO_SYSTEM_PROMPT,
            temperature=0.1,
            response_schema=VetoDecision,
        )
        decision.agent = "Legis"
        return decision if decision.veto or decision.violated_rules else None

    def _wrap(self, answer: RegulationAnswer, *, reasoning: str) -> AgentResponse:
        return AgentResponse(
            agent="Legis",
            content=answer.model_dump(),
            reasoning=reasoning,
            confidence=answer.confidence,
        )


def _build_answer_prompt(question: str, passages: list[RetrievedChunk]) -> str:
    passage_block = "\n\n".join(
        f"[مقطع {i + 1} | المصدر: {p.source} | صفحة {p.page}"
        + (f" | القسم: {p.section}" if p.section else "")
        + f"]\n{p.text}"
        for i, p in enumerate(passages)
    )
    return dedent(
        f"""
        السؤال:
        {question}

        المقاطع المرجعية:
        {passage_block}

        أعد الإجابة بصيغة JSON مطابقة للمخطط. أدرج في citations فقط المقاطع
        التي استندت إليها فعلاً، بنفس نص المقطع ومصدره وصفحته وقسمه إن وجد.
        """
    ).strip()


def _build_veto_prompt(proposal: dict[str, Any], passages: list[RetrievedChunk]) -> str:
    passage_block = "\n\n".join(
        f"[مقطع {i + 1} | {p.source} صفحة {p.page}]\n{p.text}"
        for i, p in enumerate(passages)
    )
    return dedent(
        f"""
        الاقتراح الجاري مراجعته (JSON):
        {proposal}

        المقاطع التنظيمية ذات الصلة:
        {passage_block}

        أصدر قرارك بصيغة JSON مطابقة لمخطط VetoDecision.
        اجعل agent = "Legis" دائماً.
        """
    ).strip()


def _enforce_citations(
    answer: RegulationAnswer, passages: list[RetrievedChunk]
) -> RegulationAnswer:
    """Drop hallucinated citations; map LLM citations back to retrieved chunks."""
    by_text: dict[str, RetrievedChunk] = {p.text[:120]: p for p in passages}
    grounded: list[RegulationCitation] = []
    for cit in answer.citations:
        matched: RetrievedChunk | None = None
        key = cit.text[:120]
        if key in by_text:
            matched = by_text[key]
        else:
            for p in passages:
                if cit.text and cit.text[:80] in p.text:
                    matched = p
                    break
        if matched is None:
            continue
        grounded.append(
            RegulationCitation(
                text=matched.text,
                source=matched.source,
                page=matched.page,
                section=matched.section,
            )
        )
    answer.citations = grounded or []
    return answer


def _score_confidence(passages: list[RetrievedChunk]) -> str:
    best = min((p.score for p in passages), default=1.0)
    if best <= _STRONG_MATCH_DISTANCE:
        return "high"
    if best <= _WEAK_MATCH_DISTANCE:
        return "medium"
    return "low"


def _looks_like_schedule(proposal: dict[str, Any]) -> bool:
    if not isinstance(proposal, dict):
        return False
    if proposal.get("type") == "schedule":
        return True
    return "courses" in proposal and (
        "total_credits" in proposal or "credits" in proposal
    )


def _schedule_probe_query(proposal: dict[str, Any]) -> str:
    student = proposal.get("student") or {}
    gpa = student.get("gpa")
    credits = proposal.get("total_credits") or proposal.get("credits")
    parts = ["الحد الأقصى للساعات المسجلة", "المتطلبات السابقة"]
    if gpa is not None:
        parts.append(f"معدل الطالب {gpa}")
    if credits is not None:
        parts.append(f"عدد الساعات المقترحة {credits}")
    return " | ".join(parts)


@lru_cache(maxsize=1)
def get_legis_agent() -> LegisAgent:
    return LegisAgent()
