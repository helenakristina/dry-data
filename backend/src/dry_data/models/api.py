"""API request and response Pydantic models.

These must exactly mirror the TypeScript interfaces in frontend/src/types/api.ts.
"""

from pydantic import BaseModel, Field

from dry_data.models.warehouse import ColumnInfo


class QueryRequest(BaseModel):
    """Natural language question submitted by the user."""

    question: str = Field(min_length=1, max_length=500)


class QueryResponse(BaseModel):
    """Full response from the NL→SQL→narrative pipeline."""

    question: str
    narrative: str
    sql: str
    chart: dict | None
    error: str | None


class DatasetInfo(BaseModel):
    """Metadata for a table in the warehouse, shown in the dataset browser."""

    table_name: str
    description: str
    row_count: int
    columns: list[ColumnInfo]


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
