"""API request and response Pydantic models.

These must exactly mirror the TypeScript interfaces in frontend/src/types/api.ts.
"""

from pydantic import BaseModel, Field

from dry_data.models.warehouse import ColumnInfo, DatasetInfo  # re-exported for backward compat

__all__ = ["ColumnInfo", "DatasetInfo", "HealthResponse", "PlotlySpec", "QueryRequest", "QueryResponse"]


class QueryRequest(BaseModel):
    """Natural language question submitted by the user."""

    question: str = Field(min_length=1, max_length=500)


class PlotlySpec(BaseModel):
    """A Plotly figure specification with data traces and optional layout."""

    data: list[dict]
    layout: dict | None = None


class QueryResponse(BaseModel):
    """Full response from the NL→SQL→narrative pipeline."""

    question: str
    narrative: str
    sql: str
    chart: PlotlySpec | None
    error: str | None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
