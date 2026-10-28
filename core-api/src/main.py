"""Entrypoint for Health Core Business API (BFF)."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from contracts.envelope import UniformEnvelope
from persistence.database import init_db
from api.routes.personalization import router as personalization_router
from api.routes.ocr import router as ocr_router
from api.routes.chat import router as chat_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Core API Database models...")
    try:
        init_db()
        logger.info("Database initialized successfully.")
    except Exception as exc:
        logger.warning("Database init skipped or deferred: %s", exc)
    yield
    logger.info("Shutting down Core API...")


app = FastAPI(
    title="Health Core API (BFF)",
    version="1.0.0-beta",
    description="Business Core API & BFF Gateway for Health/InBody Agent RAG Platform",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(personalization_router)
if settings.feature_ocr_upload:
    app.include_router(ocr_router)
app.include_router(chat_router)


@app.get("/health")
async def health_check():
    return UniformEnvelope.ok({
        "service": "health-core-api",
        "status": "healthy",
        "port": settings.port,
        "database": "connected",
        "agent_service_url": settings.agent_service_url,
        "ocr_service_url": settings.ocr_service_url,
    })


@app.get("/")
async def root():
    return {
        "service": "Health Core Business API (BFF)",
        "version": "1.0.0-beta",
        "docs": "/docs",
        "status": "ok",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.port, reload=True)
