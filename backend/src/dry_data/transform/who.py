"""WHO/OWID alcohol consumption transformer.

Reads 3 raw CSVs and produces:
  - fact_global_consumption.parquet  (one row per country/year/sex)
  - dim_country.parquet              (unique country/iso3 pairs)
  - dim_year.parquet                 (unique years)

Fact rows by sex:
  'total'  → from consumption.csv, joined with share_drinkers.csv for pct_drinkers
  'male'   → from consumption_by_sex.csv, pct_drinkers is NULL
  'female' → from consumption_by_sex.csv, pct_drinkers is NULL
"""

from pathlib import Path

import polars as pl

from dry_data.exceptions import TransformError
from dry_data.transform.base import BaseTransformer
from dry_data.transform.dimensions import build_dim_country, build_dim_year, normalize_country_name

AGGREGATE_ENTITIES: frozenset[str] = frozenset(
    [
        "World",
        "Africa",
        "Asia",
        "Europe",
        "North America",
        "South America",
        "Oceania",
        "High-income countries",
        "Low-income countries",
        "Upper-middle-income countries",
        "Lower-middle-income countries",
        "European Union (27)",
        "G20",
        "G7",
    ]
)

# Possible column names from OWID CSVs (they change between dataset versions)
CONSUMPTION_VALUE_CANDIDATES = [
    "Alcohol consumption per capita \u2013 WHO version (liters of pure alcohol)",
    "total_alcohol",
]
MALE_VALUE_CANDIDATES = [
    "Alcohol consumption per capita, male \u2013 WHO version (liters of pure alcohol)",
    "male_alcohol",
]
FEMALE_VALUE_CANDIDATES = [
    "Alcohol consumption per capita, female \u2013 WHO version (liters of pure alcohol)",
    "female_alcohol",
]
SHARE_VALUE_CANDIDATES = [
    "Indicator:Alcohol, drinkers only consumption (APC) - Data by country",
    "share_drinkers",
]


def _filter_aggregates(df: pl.DataFrame) -> pl.DataFrame:
    """Remove non-country rows (aggregates, regions).

    Args:
        df: Raw DataFrame with 'Entity' and 'Code' columns.

    Returns:
        Filtered DataFrame with only country-level rows.
    """
    return df.filter(
        pl.col("Code").is_not_null()
        & (pl.col("Code") != "")
        & ~pl.col("Entity").is_in(list(AGGREGATE_ENTITIES))
    )


def _rename_columns(df: pl.DataFrame, value_col_rename: dict[str, str]) -> pl.DataFrame:
    """Rename OWID base columns (Entity, Code, Year) to canonical names.

    Args:
        df: DataFrame with OWID column names.
        value_col_rename: Extra column renames (source name → canonical name).

    Returns:
        DataFrame with renamed columns.
    """
    all_renames = {"Entity": "country_name", "Code": "iso3", "Year": "year", **value_col_rename}
    existing = {k: v for k, v in all_renames.items() if k in df.columns}
    return df.rename(existing)


def _detect_value_col(df: pl.DataFrame, candidates: list[str]) -> str:
    """Return the first candidate column name that exists in df.

    Args:
        df: DataFrame to inspect.
        candidates: Ordered list of column names to try.

    Returns:
        First matching column name.

    Raises:
        TransformError: If no candidate column is found.
    """
    for col in candidates:
        if col in df.columns:
            return col
    raise TransformError(f"Expected one of {candidates} but found columns: {df.columns}")


def _validate_no_nulls(df: pl.DataFrame, cols: list[str]) -> None:
    """Raise TransformError if any required column has null values.

    Args:
        df: DataFrame to validate.
        cols: Column names that must be non-null.

    Raises:
        TransformError: If any null is found.
    """
    for col in cols:
        null_count = df[col].null_count()
        if null_count > 0:
            raise TransformError(f"Found {null_count} null values in required column '{col}'")


class WHOTransformer(BaseTransformer):
    """Transforms WHO/OWID CSVs into fact and dimension Parquet files."""

    _raw_dir_override: Path | None = None
    _cleaned_dir_override: Path | None = None

    @property
    def source_name(self) -> str:
        """Identifier matching WHOIngestor.source_name."""
        return "who"

    @property
    def raw_dir(self) -> Path:
        if self._raw_dir_override is not None:
            return self._raw_dir_override
        return super().raw_dir

    @property
    def cleaned_dir(self) -> Path:
        if self._cleaned_dir_override is not None:
            return self._cleaned_dir_override
        return super().cleaned_dir

    def transform(self) -> list[Path]:
        """Read raw CSVs, clean, merge, and write Parquet outputs.

        Returns:
            List of paths to written Parquet files.

        Raises:
            TransformError: If data validation fails or required columns are absent.
        """
        try:
            consumption_raw = pl.read_csv(self.raw_dir / "consumption.csv")
            by_sex_raw = pl.read_csv(self.raw_dir / "consumption_by_sex.csv")
            share_raw = pl.read_csv(self.raw_dir / "share_drinkers.csv")
        except Exception as exc:
            raise TransformError(f"Failed to read WHO raw CSVs: {exc}") from exc

        total_df = self._build_total_rows(consumption_raw, share_raw)
        male_df, female_df = self._build_sex_rows(by_sex_raw)

        fact_df = pl.concat([total_df, male_df, female_df])

        _validate_no_nulls(fact_df, ["iso3", "year"])

        dim_country_df = build_dim_country(fact_df)
        dim_year_df = build_dim_year(fact_df)

        return [
            self._write_parquet(fact_df, "fact_global_consumption"),
            self._write_parquet(dim_country_df, "dim_country"),
            self._write_parquet(dim_year_df, "dim_year"),
        ]

    def _build_total_rows(
        self, consumption_raw: pl.DataFrame, share_raw: pl.DataFrame
    ) -> pl.DataFrame:
        """Build fact rows for sex='total' from consumption + share CSVs.

        Args:
            consumption_raw: Raw consumption per capita CSV data.
            share_raw: Raw share of drinkers CSV data.

        Returns:
            DataFrame with columns: country_name, iso3, year,
            liters_pure_alcohol_pc, pct_drinkers, sex.
        """
        consumption = _filter_aggregates(consumption_raw)
        total_col = _detect_value_col(consumption, CONSUMPTION_VALUE_CANDIDATES)
        consumption = consumption.with_columns(
            pl.col("Entity").map_elements(normalize_country_name, return_dtype=pl.Utf8)
        )
        consumption = _rename_columns(consumption, {total_col: "liters_pure_alcohol_pc"})
        consumption = consumption.with_columns(pl.col("year").cast(pl.Int64))

        share = _filter_aggregates(share_raw)
        share_col = _detect_value_col(share, SHARE_VALUE_CANDIDATES)
        share = _rename_columns(share, {share_col: "pct_drinkers"})
        share = share.with_columns(pl.col("year").cast(pl.Int64))
        share = share.select(["iso3", "year", "pct_drinkers"])

        fact_cols = [
            "country_name",
            "iso3",
            "year",
            "liters_pure_alcohol_pc",
            "pct_drinkers",
            "sex",
        ]
        return (
            consumption.join(share, on=["iso3", "year"], how="left")
            .with_columns(pl.lit("total").alias("sex"))
            .select(fact_cols)
        )

    def _build_sex_rows(self, by_sex_raw: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
        """Build fact rows for sex='male' and sex='female'.

        Args:
            by_sex_raw: Raw consumption by sex CSV data.

        Returns:
            Tuple of (male_df, female_df).
        """
        by_sex = _filter_aggregates(by_sex_raw)
        male_col = _detect_value_col(by_sex, MALE_VALUE_CANDIDATES)
        female_col = _detect_value_col(by_sex, FEMALE_VALUE_CANDIDATES)

        # Normalize names and rename base columns before detecting value cols
        by_sex = by_sex.with_columns(
            pl.col("Entity").map_elements(normalize_country_name, return_dtype=pl.Utf8)
        )
        by_sex = _rename_columns(by_sex, {})
        by_sex = by_sex.with_columns(pl.col("year").cast(pl.Int64))

        fact_cols = [
            "country_name",
            "iso3",
            "year",
            "liters_pure_alcohol_pc",
            "pct_drinkers",
            "sex",
        ]
        null_col = pl.lit(None).cast(pl.Float64).alias("pct_drinkers")

        male_df = (
            by_sex.select(["country_name", "iso3", "year", male_col])
            .rename({male_col: "liters_pure_alcohol_pc"})
            .with_columns([null_col, pl.lit("male").alias("sex")])
            .select(fact_cols)
        )
        female_df = (
            by_sex.select(["country_name", "iso3", "year", female_col])
            .rename({female_col: "liters_pure_alcohol_pc"})
            .with_columns([null_col, pl.lit("female").alias("sex")])
            .select(fact_cols)
        )
        return male_df, female_df
