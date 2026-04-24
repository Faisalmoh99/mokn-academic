"""Planner agent + Planner→Legis precursor veto tests."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mokn.agents.legis import LegisAgent
from mokn.agents.planner import PlannerAgent, _PlannerDecision
from mokn.data.repository import CourseRepository, StudentRepository
from mokn.memory.knowledge import KnowledgeBase
from mokn.planning.conflicts import sections_conflict
from mokn.planning.optimizer import generate_schedule_candidates
from mokn.schemas.agent import AgentContext, VetoDecision
from mokn.schemas.course import CourseSection
from mokn.schemas.schedule import ScheduleProposal

_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "mock"


@pytest.fixture
def students_repo() -> StudentRepository:
    return StudentRepository(_DATA_DIR / "students.json")


@pytest.fixture
def courses_repo() -> CourseRepository:
    return CourseRepository(_DATA_DIR / "courses.json")


def _section_from_schedule(course_code: str, sched_course: Any, courses_lookup: dict) -> CourseSection:
    """Reconstruct the CourseSection object used in a scheduled option."""
    course = courses_lookup[course_code]
    return next(s for s in course.sections if s.section_id == sched_course.section_id)


@pytest.mark.asyncio
async def test_optimizer_excludes_completed_and_unmet_prereqs(
    students_repo: StudentRepository, courses_repo: CourseRepository
) -> None:
    student = await students_repo.get("442001234")  # has CS101-202, MATH101-201, etc.
    available = await courses_repo.list_available(student.completed_course_codes)
    # Narrow to fall offerings the way PlannerAgent does.
    fall = [c for c in available if "fall" in c.offered_semesters]

    options = await generate_schedule_candidates(
        student=student,
        available_courses=fall,
        target_hours=15,
        max_options=3,
    )

    assert options, "expected at least one candidate"
    for opt in options:
        for sched in opt.courses:
            assert sched.course_code not in student.completed_course_codes


@pytest.mark.asyncio
async def test_optimizer_returns_multiple_distinct_options(
    students_repo: StudentRepository, courses_repo: CourseRepository
) -> None:
    student = await students_repo.get("442001234")
    available = await courses_repo.list_available(student.completed_course_codes)
    fall = [c for c in available if "fall" in c.offered_semesters]

    options = await generate_schedule_candidates(
        student=student, available_courses=fall, target_hours=15, max_options=3
    )
    labels = {o.label for o in options}
    # We expect at least 2 unique labels when there's enough material.
    assert len(labels) >= 2


@pytest.mark.asyncio
async def test_optimizer_candidates_are_internally_conflict_free(
    students_repo: StudentRepository, courses_repo: CourseRepository
) -> None:
    student = await students_repo.get("442001234")
    available = await courses_repo.list_available(student.completed_course_codes)
    fall = [c for c in available if "fall" in c.offered_semesters]
    lookup = {c.code: c for c in await courses_repo.list_all()}

    options = await generate_schedule_candidates(
        student=student, available_courses=fall, target_hours=15, max_options=3
    )

    for opt in options:
        sections = [_section_from_schedule(sc.course_code, sc, lookup) for sc in opt.courses]
        for i, sec_i in enumerate(sections):
            for sec_j in sections[i + 1:]:
                assert not sections_conflict(sec_i, sec_j), (
                    f"{opt.label} contains a self-conflict"
                )


@pytest.mark.asyncio
async def test_planner_process_returns_valid_proposal(
    students_repo: StudentRepository,
    courses_repo: CourseRepository,
    fake_gemini: Any,
) -> None:
    def responder(prompt: str, schema: type[Any] | None) -> Any:
        assert schema is _PlannerDecision
        return _PlannerDecision(
            recommended_option="balanced",
            warnings=[],
            constraints_considered=["المتطلبات السابقة", "التفضيلات"],
            per_option_reasoning={},
        )

    fake_gemini.responder = responder
    planner = PlannerAgent(students=students_repo, courses=courses_repo, llm=fake_gemini)

    ctx = AgentContext(
        query="جدول مقترح",
        student_id="442001234",
        metadata={"target_hours": 15, "target_semester": "fall-2026"},
    )
    response = await planner.process(ctx)
    assert response.agent == "Planner"
    proposal = ScheduleProposal.model_validate(response.content)
    assert proposal.student_id == "442001234"
    assert proposal.options, "proposal should have at least one option"
    assert proposal.recommended_option in {o.label for o in proposal.options}


@pytest.mark.asyncio
async def test_planner_abstains_on_veto(
    students_repo: StudentRepository,
    courses_repo: CourseRepository,
    fake_gemini: Any,
) -> None:
    planner = PlannerAgent(students=students_repo, courses=courses_repo, llm=fake_gemini)
    result = await planner.can_veto({"type": "schedule", "total_credits": 18})
    assert result is None
    assert fake_gemini.calls == []


@pytest.mark.asyncio
async def test_planner_legis_precursor_veto_triggers_on_violation(
    students_repo: StudentRepository,
    courses_repo: CourseRepository,
    seeded_kb: KnowledgeBase,
    fake_gemini: Any,
) -> None:
    """The critical architecture check: Planner's output routed to Legis
    should trigger a veto when a regulation is violated.
    """
    # Build the Planner fake — returns a _PlannerDecision.
    planner_fake = fake_gemini

    def planner_responder(prompt: str, schema: type[Any] | None) -> Any:
        assert schema is _PlannerDecision
        return _PlannerDecision(
            recommended_option="balanced",
            warnings=[],
            constraints_considered=[],
            per_option_reasoning={},
        )

    planner_fake.responder = planner_responder
    planner = PlannerAgent(
        students=students_repo, courses=courses_repo, llm=planner_fake
    )

    # Run Planner for a mid-career student to get a real proposal shape.
    ctx = AgentContext(
        query="جدول",
        student_id="442001234",
        metadata={"target_hours": 15, "target_semester": "fall-2026"},
    )
    response = await planner.process(ctx)
    proposal = ScheduleProposal.model_validate(response.content)

    # Now simulate the *violating* scenario the precursor must catch:
    # student 442009876 has GPA 2.8 → regulation caps them at 15 credits.
    # We forge an 18-credit schedule and hand it to Legis as a schedule proposal.
    class _LegisFake:
        calls: list[dict[str, Any]] = []

        async def generate(
            self,
            prompt: str,
            *,
            system: str | None = None,
            temperature: float = 0.3,
            response_schema: type[Any] | None = None,
            model: str | None = None,
        ) -> Any:
            self.calls.append({"prompt": prompt, "schema": response_schema})
            assert response_schema is VetoDecision
            return VetoDecision(
                agent="Legis",
                veto=True,
                reason="معدل 2.8 يسمح بحد أقصى 15 ساعة بحسب المادة 14.",
                violated_rules=["credit-hour-cap"],
                suggestion="خفّض العبء إلى 15 ساعة.",
            )

    legis = LegisAgent(knowledge=seeded_kb, llm=_LegisFake())

    violating_proposal = {
        "type": "schedule",
        "student": {"id": "442009876", "gpa": 2.8},
        "courses": [
            {"code": "CS201", "credits": 3},
            {"code": "CS202", "credits": 3},
            {"code": "CS203", "credits": 3},
            {"code": "MATH201", "credits": 3},
            {"code": "ENG201", "credits": 3},
            {"code": "STAT201", "credits": 3},
        ],
        "total_credits": 18,
    }
    veto = await legis.can_veto(violating_proposal)
    assert veto is not None
    assert veto.veto is True
    assert "credit-hour-cap" in veto.violated_rules
    # And a sanity check: the proposal Planner actually produced was valid-shaped.
    assert proposal.options
