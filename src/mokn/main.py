"""FastAPI entrypoint for Mokn Academic.

Run: `uvicorn src.mokn.main:app --reload`
"""
from __future__ import annotations

from fastapi import FastAPI

from mokn import __version__
from mokn.api.routes import legis as legis_routes
from mokn.config import configure_logging, get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        title="Mokn Academic API",
        version=__version__,
        description="Multi-agent academic advisor. Session 1: Legis agent.",
    )

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.env, "version": __version__}

    app.include_router(legis_routes.router)
    return app


app = create_app()
