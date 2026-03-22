"""Shared dimension-building utilities for all transformers.

Functions here are reused by WHO, BRFSS, FRED, and other transformers
to build consistent dimension table contributions.
"""

import polars as pl

# Known country name variants to normalize to a canonical form.
# Keys are source-specific names; values are canonical names.
COUNTRY_NAME_OVERRIDES: dict[str, str] = {
    "Turkiye": "Turkey",
    "United States of America": "United States",
    "Viet Nam": "Vietnam",
    "Republic of Korea": "South Korea",
    "Democratic Republic of Congo": "Democratic Republic of the Congo",
    "Czechia": "Czech Republic",
    "North Macedonia": "Macedonia",
    "Timor": "East Timor",
    "Micronesia (country)": "Micronesia",
    "Cape Verde": "Cabo Verde",
    "Cote d'Ivoire": "Ivory Coast",
}


def normalize_country_name(name: str) -> str:
    """Return the canonical country name for a given source name.

    Args:
        name: Country name as it appears in the source data.

    Returns:
        Canonical country name (may be the same as input if no override).
    """
    return COUNTRY_NAME_OVERRIDES.get(name, name)


def build_dim_country(df: pl.DataFrame) -> pl.DataFrame:
    """Build a deduplicated dim_country contribution from a DataFrame.

    Args:
        df: DataFrame with at least 'country_name' and 'iso3' columns.

    Returns:
        Deduplicated DataFrame with 'country_name' and 'iso3' columns.
    """
    return df.select(["country_name", "iso3"]).unique(subset=["iso3"])


def build_dim_year(df: pl.DataFrame) -> pl.DataFrame:
    """Build a deduplicated dim_year contribution from a DataFrame.

    Args:
        df: DataFrame with at least a 'year' column.

    Returns:
        Deduplicated DataFrame with a 'year' column.
    """
    return df.select(["year"]).unique()
