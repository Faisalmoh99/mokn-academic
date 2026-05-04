"""Guardian — proactive academic risk monitor.

Guardian is the fourth agent: a *suggester*, not a gatekeeper. Where
Orchestrator/Planner/Legis are reactive (they wait for the student),
Guardian scans student records on its own. The deterministic rule layer
(`mokn.monitoring.risk_rules`) decides who is at risk; this agent's only
job is to translate the assessment into a warm Arabic message and a short
list of concrete recommendations.

Crucially, Guardian does NOT veto. `can_veto` always returns None — it
informs, the student decides.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from textwrap import dedent
from typing import Any

from pydantic import BaseModel, Field

from mokn.agents.base import BaseAgent
from mokn.llm.gemini import GeminiClient, get_gemini_client
from mokn.schemas.agent import AgentContext, AgentResponse, VetoDecision
from mokn.schemas.guardian import (
    GuardianRecommendation,
    GuardianRecommendationAction,
    GuardianRecommendationPriority,
    RiskAssessment,
    RiskFactor,
)

logger = logging.getLogger(__name__)


GUARDIAN_SYSTEM_PROMPT = dedent(
    """
    أنت "Guardian" — الوكيل المراقب الاستباقي في نظام مُكِن أكاديمي.

    دورك:
    - تقيّم وضع الطالب بناءً على المؤشرات المرفقة (تم رصدها مسبقاً
      بقواعد دقيقة، لست بحاجة لإعادة الفحص ولا لاختراع مؤشرات جديدة).
    - تكتب رسالة استباقية ودودة وواضحة باللغة العربية للطالب.
    - تقترح خطوات عملية قابلة للتنفيذ، مع توضيح المنطق وراء كل اقتراح.

    قواعد صارمة:
    1. لا تفرض. اقترح فقط. القرار للطالب أو لمرشده البشري.
    2. لا تخوّف. اطرح المخاطر بهدوء مع طمأنة بأن هناك حلولاً.
    3. لا تخترع أرقاماً. استخدم فقط المؤشرات المرفقة في السياق.
    4. لهجة محترمة، مباشرة، خالية من الحشو.
    5. ابدأ الرسالة باسم الطالب الأول.
    6. أنهِ الرسالة دائماً بدعوة لتواصل مع المرشد البشري إذا احتاج تفاصيل أكثر.
    """
).strip()


class _GuardianRecommendationDraft(BaseModel):
    """LLM-produced recommendation. Validated against the schema literals
    before we hand it back to the route layer."""

    title_ar: str
    rationale_ar: str
    suggested_action: GuardianRecommendationAction
    priority: GuardianRecommendationPriority


class _GuardianOutput(BaseModel):
    """The narrow shape we ask Gemini to produce.

    We intentionally do NOT let the LLM rewrite the assessment — only the
    prose layer (message + recommendations). The risk facts are owned by
    `risk_rules`.
    """

    message_ar: str = Field(..., description="The Arabic message to the student.")
    recommendations: list[_GuardianRecommendationDraft] = Field(default_factory=list)


class GuardianAgent(BaseAgent):
    """Proactive monitor. Wraps a deterministic RiskAssessment in Arabic prose."""

    def __init__(self, llm: GeminiClient | None = None) -> None:
        self._llm = llm or get_gemini_client()

    @property
    def name(self) -> str:
        return "Guardian"

    @property
    def role_description(self) -> str:
        return "الوكيل الاستباقي لمراقبة الأداء الأكاديمي"

    @property
    def system_prompt(self) -> str:
        return GUARDIAN_SYSTEM_PROMPT

    async def process(self, context: AgentContext) -> AgentResponse:
        """Generate the proactive message + recommendations for an assessed student.

        The assessment is computed by `risk_rules.assess_student` and passed
        through `context.metadata['assessment']` (either as a dict or a
        RiskAssessment instance). Guardian's job is purely the prose layer.
        """
        assessment = _coerce_assessment(context.metadata.get("assessment"))
        prompt = _build_prompt(assessment)
        try:
            output: _GuardianOutput = await self._llm.generate(
                prompt,
                system=self.system_prompt,
                temperature=0.4,
                response_schema=_GuardianOutput,
            )
        except Exception:
            logger.exception(
                "Guardian LLM call failed for student %s; using deterministic fallback",
                assessment.student_id,
            )
            output = _fallback_output(assessment)

        recommendations = [
            GuardianRecommendation(**r.model_dump()) for r in output.recommendations
        ]
        return AgentResponse(
            agent="Guardian",
            content={
                "message_ar": output.message_ar,
                "recommendations": [r.model_dump() for r in recommendations],
                "assessment": assessment.model_dump(),
            },
            reasoning=(
                f"assessed {assessment.student_id} with severity "
                f"{assessment.overall_severity.value} and "
                f"{len(assessment.factors)} factor(s)"
            ),
            confidence=_confidence_from_severity(assessment),
        )

    async def can_veto(self, proposal: dict[str, Any]) -> VetoDecision | None:
        """Guardian does NOT veto. It only suggests."""
        return None


def _coerce_assessment(raw: Any) -> RiskAssessment:
    if raw is None:
        raise ValueError(
            "GuardianAgent.process requires context.metadata['assessment']"
        )
    if isinstance(raw, RiskAssessment):
        return raw
    if isinstance(raw, dict):
        return RiskAssessment.model_validate(raw)
    raise TypeError(
        f"GuardianAgent.process: 'assessment' must be RiskAssessment or dict, "
        f"got {type(raw).__name__}"
    )


def _build_prompt(assessment: RiskAssessment) -> str:
    factor_block = (
        "\n".join(_format_factor(i, f) for i, f in enumerate(assessment.factors, 1))
        or "لا توجد مؤشرات."
    )
    first_name = assessment.student_name.split()[0] if assessment.student_name else "الطالب"
    severity_ar = {
        "low": "منخفض",
        "medium": "متوسط",
        "high": "مرتفع",
        "critical": "حرج",
    }[assessment.overall_severity.value]
    return dedent(
        f"""
        بيانات الطالب:
        - الاسم: {assessment.student_name} (الرقم {assessment.student_id})
        - الاسم الأول للمناداة: {first_name}
        - مستوى المخاطرة الكلي: {severity_ar}

        المؤشرات المرصودة بقواعد آلية (استخدمها كما هي، لا تضف ولا تحذف):
        {factor_block}

        المطلوب:
        1. اكتب message_ar: رسالة قصيرة (3-5 جمل) موجهة لـ {first_name}،
           تذكر بالاسم، وتشير إلى أبرز مؤشر أو مؤشرين فقط، وتطمئن وتدعو
           للتواصل مع المرشد البشري عند نهاية الرسالة.
        2. اكتب recommendations: قائمة من 1 إلى 3 توصيات.
           - لكل توصية: عنوان مختصر، تبرير مربوط بمؤشر فعلي،
             وقيمة suggested_action واحدة من:
             reduce_credit_hours, drop_at_risk_course, consult_advisor,
             improve_attendance, review_study_plan
           - وقيمة priority واحدة من: info, advisory, urgent
             (urgent للحالات الحرجة فقط).
        أعد JSON مطابق لمخطط _GuardianOutput بالضبط.
        """
    ).strip()


def _format_factor(idx: int, factor: RiskFactor) -> str:
    parts = [f"[{idx}] ({factor.severity.value}) {factor.description_ar}"]
    if factor.course_code:
        parts.append(f"المادة: {factor.course_code}")
    if factor.evidence:
        parts.append(f"البيانات: {factor.evidence}")
    return " — ".join(parts)


def _fallback_output(assessment: RiskAssessment) -> _GuardianOutput:
    """Deterministic message used only when the LLM call itself fails.

    Keeps the agent functional in offline / API-down conditions without
    silently masking real LLM bugs (we always log the underlying exception).
    """
    first_name = assessment.student_name.split()[0] if assessment.student_name else "الطالب"
    if not assessment.factors:
        return _GuardianOutput(
            message_ar=(
                f"مرحباً {first_name}، لا توجد مؤشرات خطر تستدعي التدخل حالياً. "
                "تواصل مع مرشدك إذا رغبت بمراجعة خطتك."
            ),
            recommendations=[],
        )
    top = assessment.factors[0]
    return _GuardianOutput(
        message_ar=(
            f"مرحباً {first_name}، رصدنا مؤشراً يستدعي الانتباه: "
            f"{top.description_ar} ننصح بمراجعة المرشد الأكاديمي للتفاصيل."
        ),
        recommendations=[
            _GuardianRecommendationDraft(
                title_ar="مراجعة المرشد الأكاديمي",
                rationale_ar="للحصول على دعم بشري بناءً على المؤشر المرصود.",
                suggested_action="consult_advisor",
                priority="advisory",
            )
        ],
    )


def _confidence_from_severity(assessment: RiskAssessment) -> str:
    sev = assessment.overall_severity.value
    if sev == "critical":
        return "high"
    if sev == "high":
        return "high"
    if sev == "medium":
        return "medium"
    return "low"


@lru_cache(maxsize=1)
def get_guardian_agent() -> GuardianAgent:
    return GuardianAgent()
