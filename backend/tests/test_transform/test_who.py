"""Tests for the WHO transformer.

Uses real Polars DataFrames — no mocks.
Each test constructs the minimal input to exercise one behavior.
"""

import polars as pl
import pytest

from dry_data.exceptions import TransformError
from dry_data.transform.who import WHOTransformer, _filter_aggregates, _rename_columns

# Minimal valid consumption CSV content as a DataFrame
CONSUMPTION_DF = pl.DataFrame(
    {
        "Entity": ["France", "Germany", "World", "Europe"],
        "Code": ["FRA", "DEU", None, None],
        "Year": [2020, 2020, 2020, 2020],
        "total_alcohol": [12.1, 11.4, 6.0, 9.5],
    }
)

CONSUMPTION_BY_SEX_DF = pl.DataFrame(
    {
        "Entity": ["France", "Germany"],
        "Code": ["FRA", "DEU"],
        "Year": [2020, 2020],
        "male_alcohol": [18.0, 16.5],
        "female_alcohol": [6.2, 6.3],
    }
)

SHARE_DRINKERS_DF = pl.DataFrame(
    {
        "Entity": ["France", "Germany"],
        "Code": ["FRA", "DEU"],
        "Year": [2020, 2020],
        "share_drinkers": [0.72, 0.68],
    }
)


# CATCHES: Aggregate rows like "World" or "Europe" end up in fact_global_consumption,
#          inflating averages and producing nonsense country-level charts
def test_filter_aggregates_removes_null_iso3_rows():
    result = _filter_aggregates(CONSUMPTION_DF)
    assert "World" not in result["Entity"].to_list()
    assert "Europe" not in result["Entity"].to_list()
    assert result.height == 2


# CATCHES: Column rename maps "Entity" to "entity" instead of "country_name",
#          breaking all downstream joins on country_name
def test_rename_columns_maps_entity_to_country_name():
    result = _rename_columns(
        CONSUMPTION_DF.filter(pl.col("Code").is_not_null()),
        value_col_rename={"total_alcohol": "liters_pure_alcohol_pc"},
    )
    assert "country_name" in result.columns
    assert "iso3" in result.columns
    assert "year" in result.columns
    assert "Entity" not in result.columns


# CATCHES: Transform produces rows with null year values, violating NOT NULL
#          constraint and causing DuckDB load failures
def test_who_transformer_raises_on_null_year(tmp_path):
    bad_df = pl.DataFrame(
        {
            "Entity": ["France"],
            "Code": ["FRA"],
            "Year": [None],
            "total_alcohol": [12.0],
        }
    )
    transformer = WHOTransformer()
    transformer._raw_dir_override = tmp_path
    transformer._cleaned_dir_override = tmp_path / "cleaned"
    transformer._cleaned_dir_override.mkdir()

    consumption_path = tmp_path / "consumption.csv"
    bad_df.write_csv(consumption_path)
    CONSUMPTION_BY_SEX_DF.write_csv(tmp_path / "consumption_by_sex.csv")
    SHARE_DRINKERS_DF.write_csv(tmp_path / "share_drinkers.csv")

    with pytest.raises(TransformError, match="null"):
        transformer.transform()


# CATCHES: Fact rows are produced without a 'sex' column, so the database
#          can't distinguish total vs male vs female consumption
def test_who_transformer_produces_sex_column(tmp_path):
    transformer = _make_transformer_with_data(tmp_path)
    paths = transformer.transform()
    fact_path = next(p for p in paths if "fact_global_consumption" in p.name)
    fact_df = pl.read_parquet(fact_path)
    assert "sex" in fact_df.columns
    sex_values = set(fact_df["sex"].to_list())
    assert sex_values == {"total", "male", "female"}


# CATCHES: pct_drinkers is only present on 'total' rows but the transformer
#          mistakenly assigns it to male/female rows as well (always NULL or wrong)
def test_who_transformer_pct_drinkers_only_on_total_rows(tmp_path):
    transformer = _make_transformer_with_data(tmp_path)
    paths = transformer.transform()
    fact_path = next(p for p in paths if "fact_global_consumption" in p.name)
    fact_df = pl.read_parquet(fact_path)
    male_rows = fact_df.filter(pl.col("sex") == "male")
    assert male_rows["pct_drinkers"].is_null().all()


# CATCHES: Transform output schema doesn't include iso3 column needed for
#          the warehouse loader to join surrogate keys
def test_who_transformer_dim_country_parquet_has_iso3(tmp_path):
    transformer = _make_transformer_with_data(tmp_path)
    paths = transformer.transform()
    dim_path = next(p for p in paths if "dim_country" in p.name)
    dim_df = pl.read_parquet(dim_path)
    assert "iso3" in dim_df.columns
    assert "country_name" in dim_df.columns


def _make_transformer_with_data(tmp_path):
    """Helper: write sample CSVs and return a configured transformer."""
    CONSUMPTION_DF.write_csv(tmp_path / "consumption.csv")
    CONSUMPTION_BY_SEX_DF.write_csv(tmp_path / "consumption_by_sex.csv")
    SHARE_DRINKERS_DF.write_csv(tmp_path / "share_drinkers.csv")
    transformer = WHOTransformer()
    transformer._raw_dir_override = tmp_path
    transformer._cleaned_dir_override = tmp_path / "cleaned"
    transformer._cleaned_dir_override.mkdir()
    return transformer
