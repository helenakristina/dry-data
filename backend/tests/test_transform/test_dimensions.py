"""Tests for shared dimension-building utilities."""

import polars as pl

from dry_data.transform.dimensions import (
    build_dim_country,
    build_dim_year,
    normalize_country_name,
)


# CATCHES: "Turkiye" is stored raw instead of normalized to "Turkey",
#          breaking JOIN with dim_country when another source uses "Turkey"
def test_normalize_country_name_handles_turkiye():
    assert normalize_country_name("Turkiye") == "Turkey"


# CATCHES: "United States of America" stored as-is, mismatching "United States"
#          from other datasets and creating two country rows
def test_normalize_country_name_handles_usa_long_form():
    assert normalize_country_name("United States of America") == "United States"


# CATCHES: Unknown country names silently transformed to empty string
def test_normalize_country_name_passes_through_unknown():
    assert normalize_country_name("France") == "France"


# CATCHES: build_dim_country produces duplicate rows for the same iso3 code,
#          causing PRIMARY KEY violations on load
def test_build_dim_country_deduplicates():
    df = pl.DataFrame(
        {"country_name": ["France", "France", "Germany"], "iso3": ["FRA", "FRA", "DEU"]}
    )
    result = build_dim_country(df)
    assert result.height == 2
    assert set(result["iso3"].to_list()) == {"FRA", "DEU"}


# CATCHES: build_dim_country drops the iso3 column, causing FK joins to fail
def test_build_dim_country_includes_required_columns():
    df = pl.DataFrame({"country_name": ["France"], "iso3": ["FRA"]})
    result = build_dim_country(df)
    assert "country_name" in result.columns
    assert "iso3" in result.columns


# CATCHES: build_dim_year produces duplicate year rows, breaking UNIQUE constraint
def test_build_dim_year_deduplicates():
    df = pl.DataFrame({"year": [2020, 2020, 2021, 2022]})
    result = build_dim_year(df)
    assert result.height == 3
    assert set(result["year"].to_list()) == {2020, 2021, 2022}


# CATCHES: Unicode country names like "Réunion" crash the normalization function
def test_normalize_country_name_handles_unicode():
    name = "Réunion"
    result = normalize_country_name(name)
    assert isinstance(result, str)
    assert len(result) > 0
