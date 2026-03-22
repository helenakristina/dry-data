"""FastAPI application factory."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import duckdb
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI

from dry_data.api.routes import datasets, health, query, story
from dry_data.config import settings

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create shared resources once at startup and release them on shutdown.

    Opens a single read-only DuckDB connection and a single AsyncOpenAI client
    for the lifetime of the application, avoiding per-request connection overhead.
    """
    try:
        app.state.db = duckdb.connect(str(settings.db_path), read_only=True)
        logger.info("lifespan.db.connected", path=str(settings.db_path))
    except Exception as exc:
        logger.warning("lifespan.db.connect_failed", error=str(exc))
        app.state.db = None

    app.state.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    logger.info("lifespan.openai_client.created")

    yield

    if app.state.db is not None:
        app.state.db.close()
        logger.info("lifespan.db.closed")

    await app.state.openai_client.close()
    logger.info("lifespan.openai_client.closed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        A configured FastAPI instance with all routes and middleware.
    """
    app = FastAPI(
        title="Dry Data API",
        description="Alcohol trends data exploration via natural language queries.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api")
    app.include_router(datasets.router, prefix="/api")
    app.include_router(query.router, prefix="/api")
    app.include_router(story.router, prefix="/api")

    return app


app = create_app()
