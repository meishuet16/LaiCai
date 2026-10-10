"""
main.py — FastAPI application entry point for the Decision Engine.

Run with:
    uvicorn backend.decision.main:app --reload --port 8003

Or from the backend/ directory:
    uvicorn decision.main:app --reload --port 8003
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router
from .config import settings
from .dashboard_api import router as dashboard_router
from .dashboard_data import dashboard_source_status
from .database import close_pool, init_pool

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    description=(
        "RetainIQ Part 3 — Decision Engine API. "
        "Turns calibrated churn predictions into human-governed review plans. "
        "No automatic offers or outreach. All financial actions require human approval."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — restrict in production to actual frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten for production
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(dashboard_router)


@app.on_event("startup")
def startup() -> None:
    logger.info(f"Starting {settings.app_title} v{settings.app_version}")
    init_pool()
    logger.info("Decision Engine ready.")


@app.on_event("shutdown")
def shutdown() -> None:
    close_pool()
    logger.info("Decision Engine shut down.")


@app.get("/health", tags=["Health"])
def health_check() -> dict:
    dashboard = dashboard_source_status()
    return {
        "status": "ok",
        "service": "decision-engine",
        "version": settings.app_version,
        "mode": "database" if settings.database_url else "local_workspace",
        "data_mode": "authenticated_backend" if dashboard["available"] else "frontend_fixture",
        "data_tenant": dashboard["tenant_id"],
        "data_as_of": dashboard["as_of"],
        "evidence_kind": "synthetic",
    }
