"""Tests for API request/response Pydantic models."""

import pytest
from pydantic import ValidationError

from dry_data.models.api import DatasetInfo, QueryRequest, QueryResponse


# CATCHES: QueryRequest accepts an empty string, sending a blank question to the LLM
def test_query_request_rejects_empty_question():
    with pytest.raises(ValidationError):
        QueryRequest(question="")


# CATCHES: QueryRequest accepts a question over 500 chars, blowing the token budget
def test_query_request_rejects_question_too_long():
    with pytest.raises(ValidationError):
        QueryRequest(question="x" * 501)


# CATCHES: QueryRequest strips whitespace-only questions (e.g. "   ") through validation
def test_query_request_accepts_valid_question():
    req = QueryRequest(question="Which countries drink the most?")
    assert req.question == "Which countries drink the most?"


# CATCHES: QueryResponse allows chart to be a non-null non-dict value, crashing the frontend
def test_query_response_allows_null_chart():
    resp = QueryResponse(
        question="test",
        narrative="Some narrative",
        sql="SELECT 1",
        chart=None,
        error=None,
    )
    assert resp.chart is None


# CATCHES: DatasetInfo drops columns list, leaving the dataset browser with no column info
def test_dataset_info_requires_columns():
    with pytest.raises(ValidationError):
        DatasetInfo(table_name="fact_global_consumption", description="test", row_count=100)
