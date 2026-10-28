"""Entrypoint for Health Agentic AI Platform Service."""

import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from rag.search import load_search_snapshot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Agent Platform Service...")
    if os.getenv("BM25_AUTOLOAD", "true").strip().lower() in {"1", "true", "yes", "on"}:
        try:
            if load_search_snapshot():
                logger.info("BM25 search snapshot loaded successfully.")
            else:
                logger.warning("BM25 search snapshot not available; continuing with dense vector fallback.")
        except Exception as exc:
            logger.warning("BM25 snapshot autoload error: %s", exc)
    yield
    logger.info("Shutting down Agent Platform Service...")


app = FastAPI(
    title="Health Agentic Platform Service",
    version="1.0.0-beta",
    description="Stateless Multi-Agent Reasoning, Hybrid RAG, and Biometric Tools Engine",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root():
    return {
        "service": "Health Agentic AI Platform Service",
        "version": "1.0.0-beta",
        "docs": "/docs",
        "status": "ok",
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8001))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
