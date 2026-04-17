"""FastAPI dependency wiring.

Keeps FastAPI decoupled from the agent constructors — each endpoint asks
for the abstraction it needs (agent, LLM, KB), and we pick the concrete
instance here. Tests override these via `app.dependency_overrides`.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from mokn.agents.legis import LegisAgent, get_legis_agent
from mokn.config import Settings, get_settings


def settings_dep() -> Settings:
    return get_settings()


def legis_agent_dep() -> LegisAgent:
    return get_legis_agent()


SettingsDep = Annotated[Settings, Depends(settings_dep)]
LegisDep = Annotated[LegisAgent, Depends(legis_agent_dep)]
