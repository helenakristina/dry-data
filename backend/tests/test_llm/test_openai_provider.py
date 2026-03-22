"""Tests for OpenAIProvider.

Mocks AsyncOpenAI entirely — never calls the real API.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from dry_data.exceptions import LLMError
from dry_data.llm.openai_provider import OpenAIProvider
from dry_data.models.warehouse import QueryResult


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock()
    return client


@pytest.fixture
def provider(mock_client):
    return OpenAIProvider(client=mock_client, model="gpt-4o")


def _make_response(content: str):
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# CATCHES: generate_sql returns the raw markdown-fenced response instead of
#          stripping ```sql ... ``` fences, causing DuckDB to reject the query
@pytest.mark.asyncio
async def test_generate_sql_strips_markdown_fences(provider, mock_client):
    mock_client.chat.completions.create.return_value = _make_response(
        "```sql\nSELECT * FROM dim_country\n```"
    )
    sql = await provider.generate_sql("List all countries", schema_context="")
    assert sql.strip() == "SELECT * FROM dim_country"
    assert "```" not in sql


# CATCHES: generate_sql raises LLMError on API failure but swallows the
#          original exception, making it undebuggable
@pytest.mark.asyncio
async def test_generate_sql_raises_llm_error_on_failure(provider, mock_client):
    mock_client.chat.completions.create.side_effect = Exception("API down")
    with pytest.raises(LLMError, match="API down"):
        await provider.generate_sql("anything", schema_context="")


# CATCHES: narrate_results returns None instead of a string when the model
#          returns empty content
@pytest.mark.asyncio
async def test_narrate_results_returns_string(provider, mock_client):
    mock_client.chat.completions.create.return_value = _make_response(
        "France leads consumption at 12.1L."
    )
    result = QueryResult(columns=["country", "liters"], rows=[["France", 12.1]])
    narrative = await provider.narrate_results("Which country leads?", result)
    assert isinstance(narrative, str)
    assert len(narrative) > 0


# CATCHES: suggest_chart returns dict when model says "null", crashing the
#          JSON encoder downstream
@pytest.mark.asyncio
async def test_suggest_chart_returns_none_when_model_says_null(provider, mock_client):
    mock_client.chat.completions.create.return_value = _make_response("null")
    result = QueryResult(columns=["year", "count"], rows=[[2020, 5]])
    chart = await provider.suggest_chart("How many?", result)
    assert chart is None


# CATCHES: suggest_chart raises instead of returning None on malformed JSON
@pytest.mark.asyncio
async def test_suggest_chart_returns_none_on_malformed_json(provider, mock_client):
    mock_client.chat.completions.create.return_value = _make_response("not valid json {{")
    result = QueryResult(columns=["x"], rows=[[1]])
    chart = await provider.suggest_chart("anything", result)
    assert chart is None


# CATCHES: suggest_chart returns a dict (valid PlotlySpec JSON) correctly
@pytest.mark.asyncio
async def test_suggest_chart_returns_dict_on_valid_json(provider, mock_client):
    mock_client.chat.completions.create.return_value = _make_response(
        '{"data": [{"type": "bar", "x": [2020], "y": [5]}]}'
    )
    result = QueryResult(columns=["year", "count"], rows=[[2020, 5]])
    chart = await provider.suggest_chart("Bar chart please", result)
    assert isinstance(chart, dict)
    assert "data" in chart
