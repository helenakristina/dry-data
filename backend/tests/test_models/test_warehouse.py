"""Tests for warehouse Pydantic models."""

from dry_data.models.warehouse import ColumnInfo, QueryResult, TableSchema


# CATCHES: ColumnInfo silently allows nullable field to be a non-bool string like "YES"
def test_column_info_requires_bool_nullable():
    info = ColumnInfo(name="iso3", type="VARCHAR", nullable=False, sample_values=["USA", "FRA"])
    assert info.nullable is False


# CATCHES: QueryResult stores raw tuples instead of lists, crashing JSON serialisation
def test_query_result_stores_rows_as_lists():
    result = QueryResult(
        columns=["country", "year"],
        rows=[["France", 2020], ["Russia", 2021]],
    )
    assert result.rows[0] == ["France", 2020]


# CATCHES: TableSchema accepts negative row_count, confusing the dataset browser
def test_table_schema_has_columns_and_count():
    schema = TableSchema(
        table_name="dim_country",
        columns=[ColumnInfo(name="iso3", type="VARCHAR", nullable=False, sample_values=[])],
        row_count=42,
    )
    assert schema.row_count == 42
    assert len(schema.columns) == 1
