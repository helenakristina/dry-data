"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dry_data.api.routes import datasets, health, query, story


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        A configured FastAPI instance with all routes and middleware.
    """
    app = FastAPI(
        title="Dry Data API",
        description="Alcohol trends data exploration via natural language queries.",
        version="0.1.0",
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
