"""Warehouse-level Pydantic models.

Shared between repositories, services, and the MCP server.
"""

from pydantic import BaseModel


class ColumnInfo(BaseModel):
    """Metadata for a single table column."""

    name: str
    type: str
    nullable: bool
    sample_values: list[str]


class DatasetInfo(BaseModel):
    """Metadata for a table in the warehouse, shown in the dataset browser."""

    table_name: str
    description: str
    row_count: int
    columns: list[ColumnInfo]


class TableSchema(BaseModel):
    """Schema descriptor for a DuckDB table."""

    table_name: str
    columns: list[ColumnInfo]
    row_count: int


class QueryResult(BaseModel):
    """Results from a DuckDB query execution."""

    columns: list[str]
    rows: list[list]
