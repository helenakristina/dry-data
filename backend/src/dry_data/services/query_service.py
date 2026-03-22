"""Query orchestration service.

Coordinates the LLM provider and data repository to answer
natural language questions with SQL, narrative, and chart.
"""

import asyncio

import structlog

from dry_data.exceptions import LLMError
from dry_data.llm.base import LLMProviderBase
from dry_data.models.api import QueryResponse
from dry_data.warehouse.repository_base import BaseDataRepository

logger = structlog.get_logger()


class QueryService:
    """Orchestrates NL→SQL→narrate→chart for a user question."""

    def __init__(
        self,
        data_repo: BaseDataRepository,
        llm_provider: LLMProviderBase,
    ) -> None:
        self._repo = data_repo
        self._llm = llm_provider

    async def answer_question(self, question: str) -> QueryResponse:
        """Answer a natural language question about the data.

        Steps:
            1. Build schema context from available tables.
            2. Ask LLM to generate SQL.
            3. Execute SQL safely against DuckDB.
            4. Ask LLM to narrate results.
            5. Ask LLM to suggest a chart spec.

        Args:
            question: The user's natural language question.

        Returns:
            QueryResponse with sql, narrative, chart, and question fields.

        Raises:
            QueryError: If the SQL is unsafe or execution fails.
            LLMError: If the LLM API fails persistently.
        """
        schema_context = self._build_schema_context()

        sql = await self._llm.generate_sql(question, schema_context)
        logger.info("query_service.sql_generated", sql=sql[:100])

        results = self._repo.execute_safe_query(sql)
        logger.info("query_service.query_executed", rows=len(results.rows))

        narrate_task = self._llm.narrate_results(question, results)
        chart_task = self._llm.suggest_chart(question, results)

        narrate_result, chart_result = await asyncio.gather(
            narrate_task,
            chart_task,
            return_exceptions=True,
        )

        if isinstance(narrate_result, Exception):
            raise LLMError(str(narrate_result)) from narrate_result

        narrative = narrate_result
        chart = None if isinstance(chart_result, Exception) else chart_result

        return QueryResponse(
            question=question,
            sql=sql,
            narrative=narrative,
            chart=chart,
            error=None,
        )

    def _build_schema_context(self) -> str:
        """Build a compact schema string for the LLM prompt."""
        datasets = self._repo.list_tables()
        lines: list[str] = []
        for ds in datasets:
            col_str = ", ".join(f"{c.name} ({c.type})" for c in ds.columns)
            lines.append(f"- {ds.table_name}: {col_str}")
        return "\n".join(lines)
