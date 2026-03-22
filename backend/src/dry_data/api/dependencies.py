"""FastAPI dependency providers.

All wiring lives here. Routes declare their deps via Depends().
"""

from collections.abc import Generator

import duckdb
from fastapi import Depends
from openai import AsyncOpenAI

from dry_data.config import settings
from dry_data.llm.base import LLMProviderBase
from dry_data.llm.openai_provider import OpenAIProvider
from dry_data.services.query_service import QueryService
from dry_data.warehouse.repository_base import BaseDataRepository
from dry_data.warehouse.repository_who import WHORepository


def get_db_connection() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    """Yield a read-only DuckDB connection, closing it when done."""
    con = duckdb.connect(str(settings.db_path), read_only=True)
    try:
        yield con
    finally:
        con.close()


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


def get_llm_provider() -> LLMProviderBase:
    """Return the configured OpenAI LLM provider."""
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    return OpenAIProvider(client=client, model=settings.openai_model)


def get_query_service(
    repo: BaseDataRepository = Depends(get_base_data_repo),
    llm: LLMProviderBase = Depends(get_llm_provider),
) -> QueryService:
    """Return a QueryService wired to repo and LLM provider."""
    return QueryService(data_repo=repo, llm_provider=llm)
