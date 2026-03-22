"""Tests for WHORepository.

Uses real in-memory DuckDB — never mocks the database.
"""

import pytest

from dry_data.models.llm import PlotlySpec
from dry_data.warehouse.repository_who import WHORepository


@pytest.fixture
def seeded_db(sample_dim_country, sample_dim_year, sample_dim_beverage_type):
    """DB with dims and some fact_global_consumption rows."""
    db = sample_dim_country  # already contains year and beverage_type seeds too
    db.executemany(
        """INSERT INTO fact_global_consumption
           (id, country_id, year_id, beverage_type_id, liters_pure_alcohol_pc, pct_drinkers, sex)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [
            (1, 1, 1, 1, 12.1, 0.72, "total"),  # France 2020
            (2, 4, 1, 1, 11.4, 0.65, "total"),  # Germany 2020
            (3, 1, 2, 1, 12.3, 0.73, "total"),  # France 2021
            (4, 1, 1, 1, 18.0, None, "male"),   # France 2020 male
        ],
    )
    return db


# CATCHES: get_global_trend_chart returns raw dict instead of PlotlySpec,
#          breaking type checking in the API route
def test_get_global_trend_chart_returns_plotly_spec(seeded_db):
    repo = WHORepository(seeded_db)
    spec = repo.get_global_trend_chart()
    assert isinstance(spec, PlotlySpec)


# CATCHES: Chart has no data traces — empty spec renders blank chart
def test_get_global_trend_chart_has_traces(seeded_db):
    repo = WHORepository(seeded_db)
    spec = repo.get_global_trend_chart()
    assert len(spec.data) > 0


# CATCHES: Chart only returns total rows but also includes male/female rows,
#          inflating the global average
def test_get_global_trend_chart_only_uses_total_sex(seeded_db):
    repo = WHORepository(seeded_db)
    spec = repo.get_global_trend_chart()
    # Each trace y-value should reflect aggregated total rows only.
    # With 2 countries in 2020 and 1 in 2021, we expect exactly those year points.
    years_in_traces = {x for trace in spec.data for x in (trace.get("x") or [])}
    assert 2020 in years_in_traces


# CATCHES: Empty fact table causes exception instead of returning empty spec
def test_get_global_trend_chart_empty_table_returns_empty_spec(db):
    repo = WHORepository(db)
    spec = repo.get_global_trend_chart()
    assert isinstance(spec, PlotlySpec)
    assert spec.data == []
