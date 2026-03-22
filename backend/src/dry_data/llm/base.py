"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod

from dry_data.models.api import PlotlySpec
from dry_data.models.warehouse import QueryResult


class LLMProviderBase(ABC):
    """Interface that all LLM provider implementations must satisfy."""

    @abstractmethod
    async def generate_sql(self, question: str, schema_context: str) -> str:
        """Translate a natural language question into a DuckDB SQL query.

        Args:
            question: The user's natural language question.
            schema_context: Formatted table/column schema for the model.

        Returns:
            A SQL SELECT statement (no markdown fences).

        Raises:
            LLMError: On persistent API failure.
        """

    @abstractmethod
    async def narrate_results(self, question: str, results: QueryResult) -> str:
        """Produce a narrative answer from query results.

        Args:
            question: The original user question.
            results: The query result to narrate.

        Returns:
            A plain-text narrative answer.

        Raises:
            LLMError: On persistent API failure.
        """

    @abstractmethod
    async def suggest_chart(self, question: str, results: QueryResult) -> PlotlySpec | None:
        """Suggest a Plotly figure spec for the given results.

        Args:
            question: The original user question.
            results: The query result to visualize.

        Returns:
            A PlotlySpec instance, or None if no chart is appropriate.

        Raises:
            LLMError: On persistent API failure.
        """
