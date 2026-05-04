"""FastAPI entrypoint for Mokn Academic.

Run: `uvicorn src.mokn.main:app --reload`
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mokn import __version__
from mokn.api.routes import guardian as guardian_routes
from mokn.api.routes import legis as legis_routes
from mokn.api.routes import negotiate as negotiate_routes
from mokn.api.routes import planner as planner_routes
from mokn.api.routes import students as students_routes
from mokn.config import configure_logging, get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        title="Mokn Academic API",
        version=__version__,
        description="Multi-agent academic advisor. Sessions 1-3: Legis + Planner + Orchestrator negotiation.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.env, "version": __version__}

    app.include_router(legis_routes.router)
    app.include_router(planner_routes.router)
    app.include_router(negotiate_routes.router)
    app.include_router(students_routes.router)
    app.include_router(guardian_routes.router)
    return app


app = create_app()
