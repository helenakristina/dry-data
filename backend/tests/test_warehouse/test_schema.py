"""Tests for the DuckDB warehouse schema."""

from dry_data.warehouse.schema import ALL_TABLES, FACT_TABLE_INDEXES, get_table_descriptions


def test_all_tables_created(db):
    """Every table in the schema should exist in the database."""
    result = db.execute("SHOW TABLES").fetchall()
    created_tables = {row[0] for row in result}

    for table_name in ALL_TABLES:
        assert table_name in created_tables, f"Missing table: {table_name}"


def test_dim_year_insert_and_query(sample_dim_year):
    """Dimension tables should accept inserts and return data."""
    rows = sample_dim_year.execute("SELECT * FROM dim_year ORDER BY year").fetchall()
    assert len(rows) == 5
    assert rows[0][1] == 2020
    assert rows[-1][1] == 2024


def test_dim_state_insert_and_query(sample_dim_state):
    """State dimension should store FIPS, abbreviation, name, and region."""
    row = sample_dim_state.execute(
        "SELECT state_name, region FROM dim_state WHERE state_abbr = 'MN'"
    ).fetchone()
    assert row[0] == "Minnesota"
    assert row[1] == "Midwest"


def test_table_descriptions_complete():
    """Every table should have a human-readable description."""
    descriptions = get_table_descriptions()
    for table_name in ALL_TABLES:
        assert table_name in descriptions, f"Missing description for: {table_name}"
        assert len(descriptions[table_name]) > 20, f"Description too short for: {table_name}"


def test_fact_table_indexes_created(db):
    """FK indexes on fact tables should exist after schema creation."""
    result = db.execute(
        "SELECT index_name FROM duckdb_indexes() WHERE table_name LIKE 'fact_%'"
    ).fetchall()
    created_index_names = {row[0] for row in result}

    for ddl in FACT_TABLE_INDEXES:
        # Extract index name: token after "INDEX IF NOT EXISTS"
        tokens = ddl.split()
        idx = tokens.index("EXISTS") + 1
        index_name = tokens[idx]
        assert index_name in created_index_names, f"Missing index: {index_name}"
