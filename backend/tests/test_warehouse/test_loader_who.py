"""Tests for the WHO warehouse loader.

Uses real in-memory DuckDB — never mocks the database.
"""

import polars as pl
import pytest

from dry_data.exceptions import WarehouseError
from dry_data.warehouse.loader_who import load_all_who, load_who_dimensions, load_who_facts


def _write_parquets(tmp_path, country_df=None, year_df=None, fact_df=None):
    """Helper: write sample Parquet files to a temp cleaned dir."""
    cleaned = tmp_path / "cleaned" / "who"
    cleaned.mkdir(parents=True, exist_ok=True)

    if country_df is None:
        country_df = pl.DataFrame({"iso3": ["FRA", "DEU"], "country_name": ["France", "Germany"]})
    if year_df is None:
        year_df = pl.DataFrame({"year": [2020, 2021]})
    if fact_df is None:
        fact_df = pl.DataFrame(
            {
                "iso3": ["FRA", "FRA", "DEU"],
                "year": [2020, 2020, 2020],
                "liters_pure_alcohol_pc": [12.1, 18.0, 11.4],
                "pct_drinkers": [0.72, None, 0.68],
                "sex": ["total", "male", "total"],
                "country_name": ["France", "France", "Germany"],
            }
        )

    country_df.write_parquet(cleaned / "dim_country.parquet")
    year_df.write_parquet(cleaned / "dim_year.parquet")
    fact_df.write_parquet(cleaned / "fact_global_consumption.parquet")
    return cleaned


# CATCHES: Dimension loader inserts duplicate country rows on re-run, violating
#          uniqueness and doubling count before fact table load
def test_load_who_dimensions_is_idempotent(db, tmp_path):
    cleaned = _write_parquets(tmp_path)
    load_who_dimensions(db, cleaned)
    load_who_dimensions(db, cleaned)
    count = db.execute("SELECT count(*) FROM dim_country").fetchone()[0]
    assert count == 2  # not 4


# CATCHES: Fact loader appends rows on re-run instead of replacing,
#          causing row counts to double each pipeline run
def test_load_who_facts_is_idempotent(db, tmp_path):
    cleaned = _write_parquets(tmp_path)
    load_who_dimensions(db, cleaned)
    load_who_facts(db, cleaned)
    load_who_facts(db, cleaned)
    count = db.execute("SELECT count(*) FROM fact_global_consumption").fetchone()[0]
    assert count == 3  # not 6


# CATCHES: Loader stores NULL country_id on fact rows because it fails to
#          look up the surrogate key from dim_country after inserting dimensions
def test_load_who_facts_resolves_surrogate_keys(db, tmp_path):
    cleaned = _write_parquets(tmp_path)
    load_all_who(db, cleaned)
    nulls = db.execute(
        "SELECT count(*) FROM fact_global_consumption WHERE country_id IS NULL"
    ).fetchone()[0]
    assert nulls == 0


# CATCHES: Loader silently ignores schema mismatch and loads nothing,
#          leaving the table empty with no error raised
def test_load_who_dimensions_raises_on_missing_parquet(db, tmp_path):
    bad_cleaned = tmp_path / "cleaned" / "who"
    bad_cleaned.mkdir(parents=True)
    # No parquet files written
    with pytest.raises(WarehouseError):
        load_who_dimensions(db, bad_cleaned)


# CATCHES: Fact rows loaded without matching dim_year entries,
#          leaving year_id NULL on all fact rows
def test_load_all_who_populates_dim_year(db, tmp_path):
    cleaned = _write_parquets(tmp_path)
    load_all_who(db, cleaned)
    count = db.execute("SELECT count(*) FROM dim_year").fetchone()[0]
    assert count >= 2  # at least 2020, 2021


# CATCHES: beverage_type_id is NULL on all fact rows because the loader
#          never seeds dim_beverage_type with a 'total' entry
def test_load_all_who_beverage_type_id_not_null(db, tmp_path):
    cleaned = _write_parquets(tmp_path)
    load_all_who(db, cleaned)
    nulls = db.execute(
        "SELECT count(*) FROM fact_global_consumption WHERE beverage_type_id IS NULL"
    ).fetchone()[0]
    assert nulls == 0
