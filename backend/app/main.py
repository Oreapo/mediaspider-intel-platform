from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import (
    analysis_router,
    cases_router,
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


app = FastAPI(
    title="MediaSpider Intelligence Platform API",
    description="Next-generation multi-platform intelligence backend scaffold.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(platforms_router, prefix="/api")
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


@app.get("/health")
def health_check():
    return {"status": "ok"}
