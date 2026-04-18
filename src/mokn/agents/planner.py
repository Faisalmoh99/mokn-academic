"""Planner — builds ranked schedule options for a student.

The agent splits work cleanly:
  * Deterministic layer (`mokn.planning.optimizer`) enumerates schedule
    candidates. No LLM touches courses or times — prevents hallucinated
    sections.
  * LLM layer picks the recommended option, writes Arabic reasoning,
    and surfaces warnings specific to the student's record.

Planner is a proposer, not a judge — `can_veto` stays abstaining. Legis
holds veto authority over regulation violations.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from textwrap import dedent
from typing import Any

from pydantic import BaseModel, Field

from mokn.agents.base import BaseAgent
from mokn.data.repository import (
    CourseRepository,
    StudentRepository,
    get_course_repository,
    get_student_repository,
)
from mokn.llm.gemini import GeminiClient, get_gemini_client
from mokn.planning.optimizer import HardConstraints, generate_schedule_candidates
from mokn.schemas.agent import AgentContext, AgentResponse
from mokn.schemas.schedule import ScheduleOption, ScheduleProposal
from mokn.schemas.student import Student

logger = logging.getLogger(__name__)


PLANNER_SYSTEM_PROMPT = dedent(
    """
    أنت "Planner" — الوكيل المتخصص في بناء الجداول الدراسية.
    دورك: تحليل خيارات الجداول المقترحة من المحرك، واختيار الأفضل
    بناءً على سجل الطالب وتفضيلاته.

    قواعد صارمة:
    1. لا تخترع مواد أو أقسام — استخدم فقط ما يعطيه المحرك.
    2. وضح السبب وراء كل توصية.
    3. إذا كان الطالب يواجه مخاطر (تعثر سابق، غياب عالي)، وصِ بخيار متحفظ.
    4. أجب بالعربية.
    """
).strip()


class _PlannerDecision(BaseModel):
    """What Gemini returns after reviewing deterministic candidates.

    Kept narrow so the LLM cannot rewrite course codes, times, or sections.
    """

    recommended_option: str = Field(..., description="Label of the recommended option.")
    warnings: list[str] = Field(default_factory=list)
    constraints_considered: list[str] = Field(default_factory=list)
    per_option_reasoning: dict[str, str] = Field(
        default_factory=dict,
        description="Optional override reasoning keyed by option label.",
    )


class PlannerAgent(BaseAgent):
    """Schedule builder. Deterministic solver + LLM reasoning layer."""

    def __init__(
        self,
        students: StudentRepository | None = None,
        courses: CourseRepository | None = None,
        llm: GeminiClient | None = None,
        max_options: int = 3,
    ) -> None:
        self._students = students or get_student_repository()
        self._courses = courses or get_course_repository()
        self._llm = llm or get_gemini_client()
        self._max_options = max_options

    @property
    def name(self) -> str:
        return "Planner"

    @property
    def role_description(self) -> str:
        return "مهندس الجداول الدراسية المثلى"

    @property
    def system_prompt(self) -> str:
        return PLANNER_SYSTEM_PROMPT

    async def process(self, context: AgentContext) -> AgentResponse:
        student_id = context.student_id or context.metadata.get("student_id")
        target_hours = int(context.metadata.get("target_hours", 15))
        target_semester = str(context.metadata.get("target_semester", "fall"))
        prior_objections = list(context.metadata.get("prior_objections", []))
        constraints = _coerce_constraints(context.metadata.get("hard_constraints"))
        if not student_id:
            raise ValueError("PlannerAgent.process requires a student_id")

        student = await self._students.get(student_id)
        eligible = await self._eligible_courses(student, target_semester)

        options = await generate_schedule_candidates(
            student=student,
            available_courses=eligible,
            target_hours=target_hours,
            max_options=self._max_options,
            constraints=constraints,
        )

        if not options:
            return self._empty_response(student, target_semester, target_hours)

        decision = await self._rank_with_llm(
            student, options, target_hours, target_semester, prior_objections
        )
        proposal = self._assemble(student, options, decision, target_semester)
        return AgentResponse(
            agent="Planner",
            content=proposal.model_dump(),
            reasoning=f"built {len(options)} candidates; recommended {proposal.recommended_option}",
            confidence=_confidence_from_student(student),
        )

    async def _eligible_courses(self, student: Student, target_semester: str):
        available = await self._courses.list_available(student.completed_course_codes)
        # Narrow to the target semester so we don't propose spring-only courses in fall.
        from mokn.data.repository import _normalize_semester  # local import: private util

        term = _normalize_semester(target_semester)
        filtered = [c for c in available if term in c.offered_semesters]
        # Never propose a course the student is currently taking.
        current = set(student.current_courses)
        return [c for c in filtered if c.code not in current]

    async def _rank_with_llm(
        self,
        student: Student,
        options: list[ScheduleOption],
        target_hours: int,
        target_semester: str,
        prior_objections: list[str] | None = None,
    ) -> _PlannerDecision:
        prompt = _build_ranking_prompt(
            student, options, target_hours, target_semester, prior_objections or []
        )
        decision: _PlannerDecision = await self._llm.generate(
            prompt,
            system=self.system_prompt,
            temperature=0.3,
            response_schema=_PlannerDecision,
        )
        valid_labels = {o.label for o in options}
        if decision.recommended_option not in valid_labels:
            # LLM drifted — fall back to the balanced/first option.
            decision.recommended_option = next(
                (o.label for o in options if o.label == "balanced"),
                options[0].label,
            )
        return decision

    def _assemble(
        self,
        student: Student,
        options: list[ScheduleOption],
        decision: _PlannerDecision,
        target_semester: str,
    ) -> ScheduleProposal:
        # Let the LLM enrich per-option reasoning, but keep the deterministic fallback.
        for opt in options:
            override = decision.per_option_reasoning.get(opt.label)
            if override:
                opt.reasoning = override

        warnings = list(decision.warnings)
        warnings.extend(_automatic_warnings(student, options))

        constraints = list(decision.constraints_considered) or [
            "المتطلبات السابقة للمواد",
            "تعارضات الأوقات بين الأقسام",
            "تفضيلات الطالب للأيام والأوقات",
        ]

        return ScheduleProposal(
            student_id=student.student_id,
            target_semester=target_semester,
            options=options,
            recommended_option=decision.recommended_option,
            warnings=_dedupe(warnings),
            constraints_considered=_dedupe(constraints),
        )

    def _empty_response(
        self, student: Student, target_semester: str, target_hours: int
    ) -> AgentResponse:
        placeholder = ScheduleOption(
            label="empty",
            courses=[],
            total_credits=0,
            estimated_difficulty=0.0,
            reasoning="لا توجد مواد مؤهلة للطالب في هذا الفصل.",
        )
        proposal = ScheduleProposal(
            student_id=student.student_id,
            target_semester=target_semester,
            options=[placeholder],
            recommended_option="empty",
            warnings=["لا توجد مواد متاحة تستوفي المتطلبات السابقة للطالب."],
            constraints_considered=["المتطلبات السابقة", "الفصل المستهدف"],
        )
        return AgentResponse(
            agent="Planner",
            content=proposal.model_dump(),
            reasoning=f"no eligible courses for student {student.student_id} in {target_semester}",
            confidence="low",
        )


def _build_ranking_prompt(
    student: Student,
    options: list[ScheduleOption],
    target_hours: int,
    target_semester: str,
    prior_objections: list[str] | None = None,
) -> str:
    option_block = "\n\n".join(
        dedent(
            f"""
            [خيار: {o.label}]
            - عدد الساعات: {o.total_credits}
            - الصعوبة التقديرية: {o.estimated_difficulty}
            - المواد: {", ".join(o.course_codes)}
            - ملاحظة أولية: {o.reasoning}
            """
        ).strip()
        for o in options
    )
    notes_block = "\n".join(f"- {n}" for n in student.memory_notes) or "لا توجد ملاحظات."
    attendance_block = (
        "\n".join(
            f"- {code}: {rec.absences}/{rec.limit} غياب"
            for code, rec in student.attendance.items()
        )
        or "لا توجد بيانات حضور لهذا الفصل."
    )
    objections = prior_objections or []
    objections_block = ""
    if objections:
        joined = "\n".join(f"- {obj}" for obj in objections)
        objections_block = dedent(
            f"""
            سابقاً اعترض Legis بما يلي في جولات سابقة — تجنب تكرار نفس المخالفة:
            {joined}
            """
        ).strip()
    return dedent(
        f"""
        بيانات الطالب:
        - الاسم: {student.name}
        - المعدل التراكمي: {student.gpa}
        - الساعات المنجزة: {student.completed_credits}/{student.total_credits_required}
        - التفضيلات: {student.preferences.model_dump()}
        - ملاحظات:
        {notes_block}
        - بيانات الحضور:
        {attendance_block}

        الهدف: {target_hours} ساعة في فصل {target_semester}.

        {objections_block}

        الخيارات المقترحة من المحرك:
        {option_block}

        اختر الخيار الأنسب (recommended_option) مع تعليلات مختصرة لكل خيار في
        per_option_reasoning، وأضف تحذيرات (warnings) إن كان سجل الطالب يدعو لذلك،
        وعدّد القيود (constraints_considered) التي أخذتها بالحسبان.
        أعد النتيجة JSON مطابق لمخطط _PlannerDecision.
        """
    ).strip()


def _coerce_constraints(raw: Any | None) -> HardConstraints | None:
    if raw is None:
        return None
    if isinstance(raw, HardConstraints):
        return raw
    if not isinstance(raw, dict):
        return None
    return HardConstraints(
        min_credits=raw.get("min_credits"),
        max_credits=raw.get("max_credits"),
        excluded_courses=set(raw.get("excluded_courses") or []),
        required_courses=set(raw.get("required_courses") or []),
    )


def _automatic_warnings(student: Student, options: list[ScheduleOption]) -> list[str]:
    warnings: list[str] = []
    if student.gpa < 2.5:
        warnings.append("المعدل التراكمي منخفض — يُفضّل الخيار المتحفظ.")
    if student.max_absence_rate >= 0.66:
        warnings.append("نسبة الغياب الحالية مرتفعة؛ يقترب الطالب من الحرمان.")
    heaviest = max((o.total_credits for o in options), default=0)
    if heaviest > 18:
        warnings.append("أحد الخيارات يتجاوز 18 ساعة — يحتاج موافقة خاصة.")
    return warnings


def _confidence_from_student(student: Student) -> str:
    if student.gpa >= 3.5 and student.max_absence_rate < 0.3:
        return "high"
    if student.gpa < 2.5 or student.max_absence_rate >= 0.66:
        return "medium"
    return "medium"


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


@lru_cache(maxsize=1)
def get_planner_agent() -> PlannerAgent:
    return PlannerAgent()
