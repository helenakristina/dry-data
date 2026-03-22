"""Integration tests for FastAPI routes.

Uses httpx.AsyncClient with the real app, real in-memory DuckDB,
and a mocked LLM provider.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from dry_data.api.app import create_app
from dry_data.api.dependencies import get_db_connection, get_llm_provider
from dry_data.exceptions import LLMError, QueryError


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.generate_sql = AsyncMock(return_value="SELECT 1 AS n")
    llm.narrate_results = AsyncMock(return_value="There is one row.")
    llm.suggest_chart = AsyncMock(return_value=None)
    return llm


@pytest.fixture
def app(db, mock_llm):
    """App with in-memory DuckDB and mocked LLM provider."""
    application = create_app()
    application.dependency_overrides[get_db_connection] = lambda: db
    application.dependency_overrides[get_llm_provider] = lambda: mock_llm
    return application


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# CATCHES: GET /api/health returns 404 — route not registered
async def test_health_returns_200(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# CATCHES: GET /api/datasets raises 500 because list_tables crashes on empty DB
async def test_datasets_returns_list(client):
    response = await client.get("/api/datasets")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# CATCHES: POST /api/query returns 422 on empty question instead of passing
#          validation through QueryRequest
async def test_query_rejects_empty_question(client):
    response = await client.post("/api/query", json={"question": ""})
    assert response.status_code == 422


# CATCHES: POST /api/query returns 500 instead of 400 when QueryError is raised
async def test_query_returns_400_on_query_error(client, app, mock_llm):
    mock_llm.generate_sql = AsyncMock(side_effect=QueryError("bad sql"))
    response = await client.post("/api/query", json={"question": "Drop all tables"})
    assert response.status_code == 400


# CATCHES: POST /api/query returns 500 instead of 502 when LLMError is raised
async def test_query_returns_502_on_llm_error(client, app, mock_llm):
    mock_llm.generate_sql = AsyncMock(side_effect=LLMError("model offline"))
    response = await client.post("/api/query", json={"question": "What years?"})
    assert response.status_code == 502


# CATCHES: POST /api/query returns 200 but response doesn't match QueryResponse schema
async def test_query_returns_query_response_shape(client):
    response = await client.post("/api/query", json={"question": "How many rows?"})
    assert response.status_code == 200
    body = response.json()
    assert "question" in body
    assert "sql" in body
    assert "narrative" in body
    assert "chart" in body


# CATCHES: GET /api/story/global-trend returns 404 — route not registered
async def test_story_global_trend_returns_plotly_spec(client):
    response = await client.get("/api/story/global-trend")
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
