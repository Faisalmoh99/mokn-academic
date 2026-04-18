"""Orchestrator — the meta-agent that routes, moderates, and synthesizes.

Unlike Legis or Planner, Orchestrator never interprets regulations and never
writes course codes. It does exactly three jobs:

1. Classify the student's intent (regulation question vs. schedule request).
2. Act as the conductor inside the LangGraph negotiation loop — its routing
   logic lives in `mokn.negotiation.routing`, not here, because LangGraph
   needs plain functions it can bind as conditional edges.
3. Synthesize the final Arabic reply once Planner and Legis converge (or
   deadlock).

`process()` is intentionally un-implemented: Orchestrator is invoked only via
`build_negotiation_graph()`, never directly by an HTTP route.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from textwrap import dedent
from typing import Literal

from pydantic import BaseModel, Field

from mokn.agents.base import BaseAgent
from mokn.llm.gemini import GeminiClient, get_gemini_client
from mokn.schemas.agent import AgentContext, AgentResponse, VetoDecision
from mokn.schemas.regulations import RegulationAnswer
from mokn.schemas.schedule import ScheduleProposal

logger = logging.getLogger(__name__)


ORCHESTRATOR_SYSTEM_PROMPT = dedent(
    """
    أنت "Orchestrator" — قائد فريق من الوكلاء الأكاديميين.
    دورك:
    1. فهم طلب الطالب وتصنيف نيته.
    2. توزيع المهام على الوكلاء المناسبين (Legis للوائح، Planner للجداول).
    3. إدارة النقاش بين الوكلاء عند الاختلاف.
    4. تجميع النتائج في رد موحد للطالب بالعربية.

    أنت لا تفتي في اللوائح (ذلك دور Legis) ولا تبني الجداول (ذلك دور Planner).
    """
).strip()


class IntentClassification(BaseModel):
    """What the Orchestrator extracts from a free-text request."""

    intent: Literal["regulation_question", "build_schedule", "unknown"]
    target_hours: int | None = Field(
        default=None,
        ge=3,
        le=24,
        description="Extracted only when intent is build_schedule.",
    )
    target_semester: str | None = Field(
        default=None,
        description="e.g. 'fall-2026'. Fall back to next regular semester if missing.",
    )
    rationale: str = Field(
        default="",
        description="Short Arabic note on why this intent was chosen.",
    )


class OrchestratorAgent(BaseAgent):
    """Routing + synthesis. No domain expertise of its own."""

    def __init__(
        self,
        llm: GeminiClient | None = None,
        default_semester: str = "fall-2026",
        default_target_hours: int = 15,
    ) -> None:
        self._llm = llm or get_gemini_client()
        self._default_semester = default_semester
        self._default_target_hours = default_target_hours

    @property
    def name(self) -> str:
        return "Orchestrator"

    @property
    def role_description(self) -> str:
        return "المنسق الرئيسي بين الوكلاء"

    @property
    def system_prompt(self) -> str:
        return ORCHESTRATOR_SYSTEM_PROMPT

    async def classify_intent(self, request: str) -> IntentClassification:
        prompt = _build_classify_prompt(request, self._default_semester)
        decision: IntentClassification = await self._llm.generate(
            prompt,
            system=self.system_prompt,
            temperature=0.1,
            response_schema=IntentClassification,
        )
        if decision.intent == "build_schedule":
            if decision.target_hours is None:
                decision.target_hours = self._default_target_hours
            if not decision.target_semester:
                decision.target_semester = self._default_semester
        return decision

    async def synthesize_final_answer(
        self,
        request: str,
        *,
        outcome: str,
        round_number: int,
        proposal: ScheduleProposal | None = None,
        legis_answer: RegulationAnswer | None = None,
        legis_objections: list[str] | None = None,
        max_rounds: int | None = None,
    ) -> str:
        """Compose the user-facing Arabic reply at the end of a session."""
        prompt = _build_synthesis_prompt(
            request=request,
            outcome=outcome,
            round_number=round_number,
            proposal=proposal,
            legis_answer=legis_answer,
            legis_objections=legis_objections or [],
            max_rounds=max_rounds,
        )
        text: str = await self._llm.generate(
            prompt,
            system=self.system_prompt,
            temperature=0.4,
        )
        return text.strip()

    async def process(self, context: AgentContext) -> AgentResponse:
        raise NotImplementedError(
            "OrchestratorAgent is invoked via build_negotiation_graph(), not directly."
        )

    async def can_veto(self, proposal: dict) -> VetoDecision | None:  # type: ignore[override]
        return None


def _build_classify_prompt(request: str, default_semester: str) -> str:
    return dedent(
        f"""
        صنّف طلب الطالب التالي إلى واحدة من:
        1. regulation_question — سؤال عن اللوائح الأكاديمية
           (مثل: "كم الحد الأقصى للساعات؟" أو "متى ينحرم الطالب من الاختبار؟")
        2. build_schedule — طلب بناء جدول دراسي
           (مثل: "أبغى جدول 15 ساعة بدون تعارض" أو "ابني لي جدول الفصل القادم")
        3. unknown — شيء آخر لا يخص الإرشاد الأكاديمي.

        إذا كان build_schedule، استخرج:
        - target_hours: عدد الساعات المذكورة (افتراضي 15 إذا لم يُذكر).
        - target_semester: الفصل المستهدف. إذا غير مذكور استخدم "{default_semester}".

        أعد النتيجة JSON مطابق لمخطط IntentClassification. اجعل rationale موجزة
        بالعربية تشرح قرار التصنيف (سطر واحد).

        الطلب:
        {request}
        """
    ).strip()


def _build_synthesis_prompt(
    *,
    request: str,
    outcome: str,
    round_number: int,
    proposal: ScheduleProposal | None,
    legis_answer: RegulationAnswer | None,
    legis_objections: list[str],
    max_rounds: int | None,
) -> str:
    if outcome == "regulation_only" and legis_answer is not None:
        citations = "\n".join(f"- {c.text}" for c in legis_answer.citations) or "—"
        return dedent(
            f"""
            الطالب سأل: {request}

            وكيل اللوائح (Legis) أجاب:
            {legis_answer.answer}

            الاستشهادات:
            {citations}

            اكتب رداً نهائياً بالعربية للطالب:
            - واضح ومباشر
            - يستند للإجابة أعلاه
            - لا تضف أي معلومة من خارج ما قاله Legis
            - لا تذكر اسم Legis للطالب
            - نبرة مرشد أكاديمي ودود
            أعد الرد فقط كنص (ليس JSON).
            """
        ).strip()

    if outcome == "approved" and proposal is not None:
        options_block = "\n\n".join(
            dedent(
                f"""
                الخيار {o.label}:
                - الساعات: {o.total_credits}
                - المواد: {", ".join(o.course_codes) or "—"}
                - ملاحظة: {o.reasoning}
                """
            ).strip()
            for o in proposal.options
        )
        warnings_block = "\n".join(f"- {w}" for w in proposal.warnings) or "—"
        return dedent(
            f"""
            الطالب طلب: {request}
            النظام توصل لجدول مقبول بعد {round_number} جولة/جولات من النقاش.

            التوصية: {proposal.recommended_option}

            الخيارات:
            {options_block}

            تحذيرات:
            {warnings_block}

            اكتب رداً نهائياً بالعربية للطالب:
            - ودود ومباشر
            - يشرح الخيار الموصى به باختصار
            - يذكر التحذيرات بلطف إذا وجدت
            - لا تكرر كلام كل وكيل على حدة
            - نبرة مرشد أكاديمي حقيقي
            أعد الرد فقط كنص (ليس JSON).
            """
        ).strip()

    if outcome in {"escalated", "max_rounds"}:
        objections_block = "\n".join(f"- {o}" for o in legis_objections) or "—"
        cap = max_rounds if max_rounds is not None else round_number
        return dedent(
            f"""
            الطالب طلب: {request}
            لم يتمكن النظام من التوصل لاتفاق بعد {cap} جولات من النقاش.

            الاعتراضات المتراكمة من Legis:
            {objections_block}

            اكتب رداً بالعربية:
            - اعتذر بلطف
            - اشرح باختصار السبب (تعارض مع اللوائح أو قيود الطالب)
            - اقترح التواصل مع المرشد الأكاديمي البشري
            - لا تكن آلياً أو فظاً
            أعد الرد فقط كنص (ليس JSON).
            """
        ).strip()

    # out_of_scope / unknown fallback
    return dedent(
        f"""
        الطالب قال: {request}
        لم يتضح للنظام ما إذا كان السؤال عن اللوائح أو طلب جدول.

        اكتب رداً قصيراً بالعربية:
        - ودود
        - يوضح أنك مرشد أكاديمي تساعد في أسئلة اللوائح وبناء الجداول
        - يطلب من الطالب إعادة الصياغة
        أعد الرد فقط كنص (ليس JSON).
        """
    ).strip()


@lru_cache(maxsize=1)
def get_orchestrator_agent() -> OrchestratorAgent:
    return OrchestratorAgent()
