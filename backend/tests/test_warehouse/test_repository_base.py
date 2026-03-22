"""Tests for BaseDataRepository.

Uses real in-memory DuckDB — never mocks the database.
"""

import pytest

from dry_data.exceptions import QueryError
from dry_data.models.api import DatasetInfo
from dry_data.models.warehouse import QueryResult, TableSchema
from dry_data.warehouse.repository_base import BaseDataRepository


# CATCHES: Repository allows DROP TABLE through SQL that contains "drop" in a
#          table or column name — validation is too naïve
def test_validate_sql_rejects_drop(db):
    repo = BaseDataRepository(db)
    with pytest.raises(QueryError, match=r"[Pp]rohibited"):
        repo.execute_safe_query("DROP TABLE dim_year")


# CATCHES: DELETE statement is accepted because validation only checks
#          uppercase and the LLM generates lowercase SQL
def test_validate_sql_rejects_delete_lowercase(db):
    repo = BaseDataRepository(db)
    with pytest.raises(QueryError, match=r"[Pp]rohibited"):
        repo.execute_safe_query("delete from dim_year")


# CATCHES: ATTACH allows mounting an external DB file for exfiltration,
#          but the validation doesn't block it
def test_validate_sql_rejects_attach(db, sample_dim_year):
    repo = BaseDataRepository(db)
    with pytest.raises(QueryError, match=r"[Pp]rohibited"):
        repo.execute_safe_query("ATTACH ':memory:' AS external")


# CATCHES: Row limit is ignored and the query returns all rows, causing
#          memory exhaustion on large tables
def test_execute_safe_query_enforces_row_limit(db, sample_dim_year):
    repo = BaseDataRepository(db)
    result = repo.execute_safe_query("SELECT * FROM dim_year", max_rows=2)
    assert isinstance(result, QueryResult)
    assert len(result.rows) <= 2


# CATCHES: execute_safe_query returns raw tuples instead of lists,
#          causing JSON serialization to fail in the API response
def test_execute_safe_query_returns_lists(db, sample_dim_year):
    repo = BaseDataRepository(db)
    result = repo.execute_safe_query("SELECT year_id, year FROM dim_year LIMIT 1")
    assert isinstance(result.rows[0], list)


# CATCHES: get_table_schema returns column names without types, leaving
#          the LLM unable to write type-appropriate SQL
def test_get_table_schema_includes_column_types(db):
    repo = BaseDataRepository(db)
    schema = repo.get_table_schema("dim_country")
    assert isinstance(schema, TableSchema)
    assert schema.table_name == "dim_country"
    assert any(col.type for col in schema.columns)


# CATCHES: get_table_schema silently returns empty list for unknown table
#          instead of raising QueryError, hiding bugs in route layer
def test_get_table_schema_raises_on_missing_table(db):
    repo = BaseDataRepository(db)
    with pytest.raises(QueryError):
        repo.get_table_schema("table_does_not_exist")


# CATCHES: list_tables omits the fact_global_consumption table because
#          get_table_descriptions() key doesn't match the actual table name
def test_list_tables_includes_fact_global_consumption(db):
    repo = BaseDataRepository(db)
    datasets = repo.list_tables()
    assert isinstance(datasets, list)
    names = [d.table_name for d in datasets]
    assert "fact_global_consumption" in names
    assert all(isinstance(d, DatasetInfo) for d in datasets)


# CATCHES: TRUNCATE slips through the blocklist and wipes a table
def test_validate_sql_rejects_truncate(db):
    repo = BaseDataRepository(db)
    with pytest.raises(QueryError, match=r"[Pp]rohibited"):
        repo.execute_safe_query("TRUNCATE TABLE dim_year")


# CATCHES: LOAD can import a native extension and execute arbitrary code
def test_validate_sql_rejects_load(db):
    repo = BaseDataRepository(db)
    with pytest.raises(QueryError, match=r"[Pp]rohibited"):
        repo.execute_safe_query("LOAD 'httpfs'")


# CATCHES: INSTALL downloads and installs a DuckDB extension
def test_validate_sql_rejects_install(db):
    repo = BaseDataRepository(db)
    with pytest.raises(QueryError, match=r"[Pp]rohibited"):
        repo.execute_safe_query("INSTALL httpfs")


# CATCHES: PRAGMA can toggle DuckDB security or memory settings
def test_validate_sql_rejects_pragma(db):
    repo = BaseDataRepository(db)
    with pytest.raises(QueryError, match=r"[Pp]rohibited"):
        repo.execute_safe_query("PRAGMA database_list")


# CATCHES: list_tables issues N+1 queries instead of batching, causing
#          excessive DuckDB round-trips when multiple tables exist
def test_list_tables_batch_query_returns_all_existing_tables(db, sample_dim_year, sample_dim_country):
    repo = BaseDataRepository(db)
    datasets = repo.list_tables()
    names = {d.table_name for d in datasets}
    # Both seeded dimension tables must appear in a single batched call
    assert "dim_year" in names
    assert "dim_country" in names
    # Every entry must be a properly populated DatasetInfo
    for dataset in datasets:
        assert isinstance(dataset, DatasetInfo)
        assert dataset.row_count >= 0
        assert len(dataset.columns) > 0
