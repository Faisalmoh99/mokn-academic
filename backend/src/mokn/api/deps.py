"""FastAPI dependency wiring.

Keeps FastAPI decoupled from the agent constructors — each endpoint asks
for the abstraction it needs (agent, LLM, KB), and we pick the concrete
instance here. Tests override these via `app.dependency_overrides`.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from mokn.agents.legis import LegisAgent, get_legis_agent
from mokn.agents.orchestrator import OrchestratorAgent, get_orchestrator_agent
from mokn.agents.planner import PlannerAgent, get_planner_agent
from mokn.config import Settings, get_settings
from mokn.data.repository import (
    CourseRepository,
    StudentRepository,
    get_course_repository,
    get_student_repository,
)
from mokn.negotiation.store import NegotiationStore, get_default_store


def settings_dep() -> Settings:
    return get_settings()


def legis_agent_dep() -> LegisAgent:
    return get_legis_agent()


def planner_agent_dep() -> PlannerAgent:
    return get_planner_agent()


def orchestrator_agent_dep() -> OrchestratorAgent:
    return get_orchestrator_agent()


def student_repo_dep() -> StudentRepository:
    return get_student_repository()


def course_repo_dep() -> CourseRepository:
    return get_course_repository()


def negotiation_store_dep() -> NegotiationStore:
    return get_default_store()


SettingsDep = Annotated[Settings, Depends(settings_dep)]
LegisDep = Annotated[LegisAgent, Depends(legis_agent_dep)]
PlannerDep = Annotated[PlannerAgent, Depends(planner_agent_dep)]
OrchestratorDep = Annotated[OrchestratorAgent, Depends(orchestrator_agent_dep)]
StudentRepoDep = Annotated[StudentRepository, Depends(student_repo_dep)]
CourseRepoDep = Annotated[CourseRepository, Depends(course_repo_dep)]
NegotiationStoreDep = Annotated[NegotiationStore, Depends(negotiation_store_dep)]
