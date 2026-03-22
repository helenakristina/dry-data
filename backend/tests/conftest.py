"""Shared test fixtures for Dry Data.

Provides an in-memory DuckDB connection and small sample DataFrames
so tests don't need real data files or a persistent database.
"""

import duckdb
import polars as pl
import pytest

from dry_data.warehouse.schema import create_all_tables


@pytest.fixture
def db() -> duckdb.DuckDBPyConnection:
    """In-memory DuckDB with the full star schema created."""
    con = duckdb.connect(":memory:")
    create_all_tables(con)
    yield con
    con.close()


@pytest.fixture
def sample_dim_year(db: duckdb.DuckDBPyConnection) -> duckdb.DuckDBPyConnection:
    """Seed dim_year with a few test years."""
    db.executemany(
        "INSERT INTO dim_year (year_id, year) VALUES (?, ?)",
        [(1, 2020), (2, 2021), (3, 2022), (4, 2023), (5, 2024)],
    )
    return db


@pytest.fixture
def sample_dim_state(db: duckdb.DuckDBPyConnection) -> duckdb.DuckDBPyConnection:
    """Seed dim_state with a few test states."""
    db.executemany(
        "INSERT INTO dim_state VALUES (?, ?, ?, ?, ?, ?)",
        [
            (1, "27", "MN", "Minnesota", "Midwest", "West North Central"),
            (2, "06", "CA", "California", "West", "Pacific"),
            (3, "36", "NY", "New York", "Northeast", "Middle Atlantic"),
        ],
    )
    return db


@pytest.fixture
def sample_dim_country(db: duckdb.DuckDBPyConnection) -> duckdb.DuckDBPyConnection:
    """Seed dim_country with countries used in WHO tests."""
    db.executemany(
        "INSERT INTO dim_country (country_id, iso3, country_name) VALUES (?, ?, ?)",
        [
            (1, "FRA", "France"),
            (2, "RUS", "Russia"),
            (3, "USA", "United States"),
            (4, "DEU", "Germany"),
            (5, "CHN", "China"),
        ],
    )
    return db


@pytest.fixture
def sample_dim_beverage_type(db: duckdb.DuckDBPyConnection) -> duckdb.DuckDBPyConnection:
    """Seed dim_beverage_type with the 'total' beverage used by WHO data."""
    db.execute(
        "INSERT INTO dim_beverage_type (beverage_type_id, beverage_name) VALUES (1, 'total')"
    )
    return db


@pytest.fixture
def sample_brfss_df() -> pl.DataFrame:
    """Small BRFSS-like DataFrame for transform tests."""
    return pl.DataFrame(
        {
            "year": [2022, 2022, 2023, 2023],
            "state_fips": ["27", "06", "27", "36"],
            "sex": ["M", "F", "F", "M"],
            "drink_days_30d": [4, 0, 8, 15],
            "avg_drinks_occasion": [2.5, 0.0, 1.5, 3.0],
            "binge_episodes_30d": [1, 0, 0, 4],
            "heavy_drinker": [False, False, False, True],
            "sample_weight": [1.2, 0.8, 1.1, 0.9],
        }
    )
