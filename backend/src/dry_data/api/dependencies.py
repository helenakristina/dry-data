"""FastAPI dependency providers.

All wiring lives here. Routes declare their deps via Depends().
"""

import duckdb
from fastapi import Depends, Request

from dry_data.config import settings
from dry_data.llm.base import LLMProviderBase
from dry_data.llm.openai_provider import OpenAIProvider
from dry_data.services.query_service import QueryService
from dry_data.warehouse.repository_base import BaseDataRepository
from dry_data.warehouse.repository_who import WHORepository


def get_db_connection(request: Request) -> duckdb.DuckDBPyConnection:
    """Return the shared read-only DuckDB connection from app state."""
    return request.app.state.db


def get_base_data_repo(
    con: duckdb.DuckDBPyConnection = Depends(get_db_connection),
) -> BaseDataRepository:
    """Return a BaseDataRepository for the given connection."""
    return BaseDataRepository(con)


def get_who_repo(
    con: duckdb.DuckDBPyConnection = Depends(get_db_connection),
) -> WHORepository:
    """Return a WHORepository for the given connection."""
    return WHORepository(con)


def get_llm_provider(request: Request) -> LLMProviderBase:
    """Return the configured LLM provider using the shared OpenAI client."""
    return OpenAIProvider(
        client=request.app.state.openai_client,
        model=settings.openai_model,
    )


def get_query_service(
    repo: BaseDataRepository = Depends(get_base_data_repo),
    llm: LLMProviderBase = Depends(get_llm_provider),
) -> QueryService:
    """Return a QueryService wired to repo and LLM provider."""
    return QueryService(data_repo=repo, llm_provider=llm)
