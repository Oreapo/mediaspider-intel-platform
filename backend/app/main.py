from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.dependencies import container
from .api.routes import (
    analysis_router,
    auth_router,
    cases_router,
    dashboard_router,
    datasets_router,
    entities_router,
    evidence_router,
    logs_router,
    notifications_router,
    platforms_router,
    reports_router,
    signals_router,
    tasks_router,
)

DEFAULT_CORS_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:4173",
    "http://localhost:4173",
    "http://localhost:8080",
)


def cors_origins_from_env() -> list[str]:
    return [
        origin.strip()
        for origin in os.getenv("MEDIASPIDER_CORS_ORIGINS", ",".join(DEFAULT_CORS_ORIGINS)).split(",")
        if origin.strip()
    ]


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("MEDIASPIDER_SCHEDULER_ENABLED", "false").lower() == "true":
        container.scheduler_service.start()
    try:
        yield
    finally:
        await container.scheduler_service.stop()


app = FastAPI(
    title="MediaSpider Intelligence Platform API",
    description="Next-generation multi-platform intelligence backend scaffold.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_from_env(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(platforms_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")
app.include_router(datasets_router, prefix="/api")
app.include_router(analysis_router, prefix="/api")
app.include_router(signals_router, prefix="/api")
app.include_router(entities_router, prefix="/api")
app.include_router(cases_router, prefix="/api")
app.include_router(evidence_router, prefix="/api")
app.include_router(notifications_router, prefix="/api")
app.include_router(logs_router, prefix="/api")
app.include_router(reports_router, prefix="/api")


@app.get("/health", include_in_schema=False)
@app.get("/api/health")
def health_check():
    return {"status": "ok"}
