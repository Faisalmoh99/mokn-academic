"""FastAPI entrypoint for Mokn Academic.

Run: `uvicorn src.mokn.main:app --reload`
"""
from __future__ import annotations

from fastapi import FastAPI

from mokn import __version__
from mokn.api.routes import legis as legis_routes
from mokn.api.routes import negotiate as negotiate_routes
from mokn.api.routes import planner as planner_routes
from mokn.config import configure_logging, get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        title="Mokn Academic API",
        version=__version__,
        description="Multi-agent academic advisor. Sessions 1-3: Legis + Planner + Orchestrator negotiation.",
    )

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.env, "version": __version__}

    app.include_router(legis_routes.router)
    app.include_router(planner_routes.router)
    app.include_router(negotiate_routes.router)
    return app


app = create_app()
