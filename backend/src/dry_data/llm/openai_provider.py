"""OpenAI LLM provider implementation."""

import json
import re

import structlog
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from dry_data.exceptions import LLMError
from dry_data.llm.base import LLMProviderBase
from dry_data.llm.prompts import CHART_SYSTEM_PROMPT, NARRATION_SYSTEM_PROMPT, SQL_SYSTEM_PROMPT
from dry_data.models.warehouse import QueryResult

logger = structlog.get_logger()

_FENCE_RE = re.compile(r"```(?:sql)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _strip_fences(text: str) -> str:
    """Remove markdown code fences from LLM output."""
    match = _FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def _format_results_for_prompt(results: QueryResult) -> str:
    """Format QueryResult as a compact table string for the narration prompt."""
    if not results.rows:
        return "(no rows returned)"
    header = " | ".join(results.columns)
    rows = "\n".join(" | ".join(str(v) for v in row) for row in results.rows[:20])
    return f"{header}\n{rows}"


class OpenAIProvider(LLMProviderBase):
    """LLM provider backed by the OpenAI chat completions API."""

    def __init__(self, client: AsyncOpenAI, model: str) -> None:
        self._client = client
        self._model = model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), reraise=True)
    async def generate_sql(self, question: str, schema_context: str) -> str:
        """Generate a DuckDB SQL SELECT from a natural language question.

        Args:
            question: The user's natural language question.
            schema_context: Formatted table/column context.

        Returns:
            A clean SQL string (no markdown fences).

        Raises:
            LLMError: If the API call fails after retries.
        """
        system = SQL_SYSTEM_PROMPT.format(schema_context=schema_context)
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": question},
                ],
                temperature=0,
            )
            sql = _strip_fences(response.choices[0].message.content or "")
            logger.info("llm.generate_sql.ok", model=self._model)
            return sql
        except Exception as exc:
            logger.error("llm.generate_sql.error", error=str(exc))
            raise LLMError(str(exc)) from exc

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), reraise=True)
    async def narrate_results(self, question: str, results: QueryResult) -> str:
        """Narrate query results in plain English.

        Args:
            question: The original user question.
            results: The query results to narrate.

        Returns:
            A 1-3 sentence narrative.

        Raises:
            LLMError: If the API call fails after retries.
        """
        table = _format_results_for_prompt(results)
        user_msg = f"Question: {question}\n\nData:\n{table}"
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": NARRATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.3,
            )
            narrative = (response.choices[0].message.content or "").strip()
            logger.info("llm.narrate_results.ok")
            return narrative
        except Exception as exc:
            logger.error("llm.narrate_results.error", error=str(exc))
            raise LLMError(str(exc)) from exc

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), reraise=True)
    async def suggest_chart(self, question: str, results: QueryResult) -> dict | None:
        """Suggest a Plotly figure spec, or None if no chart is appropriate.

        Args:
            question: The original user question.
            results: The query results to visualize.

        Returns:
            A Plotly figure dict, or None.

        Raises:
            LLMError: If the API call fails after retries.
        """
        table = _format_results_for_prompt(results)
        user_msg = f"Question: {question}\n\nData:\n{table}"
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": CHART_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0,
            )
            raw = (response.choices[0].message.content or "").strip()
            if raw.lower() == "null":
                return None
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("llm.suggest_chart.bad_json", raw=raw[:100])
                return None
        except LLMError:
            raise
        except Exception as exc:
            logger.error("llm.suggest_chart.error", error=str(exc))
            raise LLMError(str(exc)) from exc
