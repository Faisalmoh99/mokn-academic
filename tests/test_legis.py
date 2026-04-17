"""LegisAgent behaviour tests with mocked Gemini and a real (fake-embedding) KB."""
from __future__ import annotations

from typing import Any

import pytest

from mokn.agents.legis import LegisAgent
from mokn.memory.knowledge import KnowledgeBase
from mokn.schemas.agent import AgentContext, VetoDecision
from mokn.schemas.regulations import RegulationAnswer, RegulationCitation


def _make_legis(kb: KnowledgeBase, gemini: Any) -> LegisAgent:
    return LegisAgent(knowledge=kb, llm=gemini)


@pytest.mark.asyncio
async def test_legis_answers_with_citations(
    seeded_kb: KnowledgeBase, fake_gemini: Any
) -> None:
    # Grab what the retriever will give us so the fake LLM can "cite" it.
    passages = await seeded_kb.query("الحد الأقصى للساعات لمعدل 2.8", top_k=5)
    assert passages, "seeded KB should return passages"
    top = passages[0]

    def responder(prompt: str, schema: type[Any] | None) -> Any:
        assert schema is RegulationAnswer
        return RegulationAnswer(
            answer="بحسب المادة 14، الطالب بمعدل 2.8 حده الأقصى 15 ساعة معتمدة.",
            citations=[
                RegulationCitation(
                    text=top.text,
                    source=top.source,
                    page=top.page,
                    section=top.section,
                )
            ],
            confidence="high",
        )

    fake_gemini.responder = responder
    legis = _make_legis(seeded_kb, fake_gemini)

    resp = await legis.process(
        AgentContext(query="كم الحد الأقصى للساعات لطالب بمعدل 2.8؟")
    )

    assert resp.agent == "Legis"
    answer = RegulationAnswer.model_validate(resp.content)
    assert "15" in answer.answer
    assert answer.citations, "citation must survive grounding"
    assert answer.citations[0].source == top.source


@pytest.mark.asyncio
async def test_legis_says_not_found_for_out_of_scope(
    seeded_kb: KnowledgeBase, fake_gemini: Any
) -> None:
    def responder(prompt: str, schema: type[Any] | None) -> Any:
        return RegulationAnswer(
            answer="لا أجد هذا في اللوائح المتاحة.",
            citations=[],
            confidence="low",
        )

    fake_gemini.responder = responder
    legis = _make_legis(seeded_kb, fake_gemini)

    resp = await legis.process(
        AgentContext(query="كم سعر الوجبة في مطعم الجامعة؟")
    )
    answer = RegulationAnswer.model_validate(resp.content)
    assert "لا أجد" in answer.answer
    assert answer.citations == []


@pytest.mark.asyncio
async def test_legis_drops_hallucinated_citations(
    seeded_kb: KnowledgeBase, fake_gemini: Any
) -> None:
    def responder(prompt: str, schema: type[Any] | None) -> Any:
        return RegulationAnswer(
            answer="نص مُختلق.",
            citations=[
                RegulationCitation(
                    text="نص غير موجود في أي مقطع استُرجع",
                    source="ghost.pdf",
                    page=99,
                )
            ],
            confidence="high",
        )

    fake_gemini.responder = responder
    legis = _make_legis(seeded_kb, fake_gemini)
    resp = await legis.process(AgentContext(query="سؤال تجريبي"))
    answer = RegulationAnswer.model_validate(resp.content)
    assert answer.citations == []


@pytest.mark.asyncio
async def test_legis_vetoes_schedule_violating_credit_hour_rule(
    seeded_kb: KnowledgeBase, fake_gemini: Any
) -> None:
    def responder(prompt: str, schema: type[Any] | None) -> Any:
        assert schema is VetoDecision
        return VetoDecision(
            agent="Legis",
            veto=True,
            reason="معدل الطالب 2.8 يسمح بحد أقصى 15 ساعة وفقاً للمادة 14.",
            violated_rules=["credit-hour-cap"],
            suggestion="خفض العبء إلى 15 ساعة.",
        )

    fake_gemini.responder = responder
    legis = _make_legis(seeded_kb, fake_gemini)

    proposal = {
        "type": "schedule",
        "student": {"id": "442001234", "gpa": 2.8},
        "courses": [
            {"code": "CS201", "credits": 3},
            {"code": "CS202", "credits": 3},
            {"code": "CS203", "credits": 3},
            {"code": "MATH201", "credits": 3},
            {"code": "EN201", "credits": 3},
            {"code": "STAT201", "credits": 3},
        ],
        "total_credits": 18,
    }

    decision = await legis.can_veto(proposal)
    assert decision is not None
    assert decision.veto is True
    assert "credit-hour-cap" in decision.violated_rules


@pytest.mark.asyncio
async def test_legis_abstains_on_non_schedule_proposal(
    seeded_kb: KnowledgeBase, fake_gemini: Any
) -> None:
    legis = _make_legis(seeded_kb, fake_gemini)
    result = await legis.can_veto({"type": "meal-plan", "id": 42})
    assert result is None
    # No LLM call should happen for unrelated proposals.
    assert fake_gemini.calls == []
