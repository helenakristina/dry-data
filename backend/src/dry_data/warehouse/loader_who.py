"""WHO data warehouse loader.

Loads cleaned WHO Parquet files into the DuckDB star schema.
Dimensions are loaded additively (future sources can add more countries/years).
Facts are replaced wholesale on each run (TRUNCATE + INSERT) for idempotency.
"""

from pathlib import Path

import duckdb
import structlog

from dry_data.exceptions import WarehouseError

logger = structlog.get_logger()

TOTAL_BEVERAGE_NAME = "total"


def _require_parquet(path: Path) -> None:
    """Raise WarehouseError if a Parquet file does not exist."""
    if not path.exists():
        raise WarehouseError(f"Expected Parquet file not found: {path}")


def _get_or_create_beverage_type(con: duckdb.DuckDBPyConnection, name: str) -> int:
    """Return the beverage_type_id for the given name, creating it if absent.

    Args:
        con: Open DuckDB connection.
        name: Beverage name (e.g. 'total').

    Returns:
        The beverage_type_id integer.
    """
    row = con.execute(
        "SELECT beverage_type_id FROM dim_beverage_type WHERE beverage_name = ?", [name]
    ).fetchone()
    if row:
        return row[0]
    max_id = con.execute(
        "SELECT COALESCE(MAX(beverage_type_id), 0) FROM dim_beverage_type"
    ).fetchone()[0]
    new_id = max_id + 1
    con.execute(
        "INSERT INTO dim_beverage_type (beverage_type_id, beverage_name) VALUES (?, ?)",
        [new_id, name],
    )
    return new_id


def load_who_dimensions(con: duckdb.DuckDBPyConnection, cleaned_dir: Path) -> None:
    """Load dim_country and dim_year from WHO Parquet files.

    Dimensions are additive: existing rows are kept, new rows are inserted.
    Uses iso3/year uniqueness to skip duplicates.

    Args:
        con: Open DuckDB connection (must be writable).
        cleaned_dir: Path to the cleaned/who/ directory with Parquet files.

    Raises:
        WarehouseError: If Parquet files are missing or loading fails.
    """
    country_parquet = cleaned_dir / "dim_country.parquet"
    year_parquet = cleaned_dir / "dim_year.parquet"
    _require_parquet(country_parquet)
    _require_parquet(year_parquet)

    try:
        # Insert countries not already present (by iso3)
        max_id = con.execute("SELECT COALESCE(MAX(country_id), 0) FROM dim_country").fetchone()[0]
        con.execute(
            f"""
            INSERT INTO dim_country (country_id, iso3, country_name)
            SELECT {max_id} + ROW_NUMBER() OVER () AS country_id,
                   iso3, country_name
            FROM read_parquet('{country_parquet}')
            WHERE iso3 NOT IN (SELECT iso3 FROM dim_country)
            """
        )
        logger.info(
            "loader_who.dim_country.loaded",
            path=str(country_parquet),
        )

        # Insert years not already present (dim_year has UNIQUE on year)
        max_year_id = con.execute("SELECT COALESCE(MAX(year_id), 0) FROM dim_year").fetchone()[0]
        con.execute(
            f"""
            INSERT INTO dim_year (year_id, year)
            SELECT {max_year_id} + ROW_NUMBER() OVER () AS year_id, year
            FROM read_parquet('{year_parquet}')
            WHERE year NOT IN (SELECT year FROM dim_year)
            """
        )
        logger.info(
            "loader_who.dim_year.loaded",
            path=str(year_parquet),
        )
    except WarehouseError:
        raise
    except Exception as exc:
        raise WarehouseError(f"Failed to load WHO dimensions: {exc}") from exc


def load_who_facts(con: duckdb.DuckDBPyConnection, cleaned_dir: Path) -> None:
    """Load fact_global_consumption from the WHO Parquet file.

    Replaces existing WHO fact rows (TRUNCATE + INSERT) for idempotency.
    Resolves surrogate keys (country_id, year_id, beverage_type_id) via joins.

    Args:
        con: Open DuckDB connection (must be writable).
        cleaned_dir: Path to the cleaned/who/ directory.

    Raises:
        WarehouseError: If Parquet file is missing or loading fails.
    """
    fact_parquet = cleaned_dir / "fact_global_consumption.parquet"
    _require_parquet(fact_parquet)

    beverage_id = _get_or_create_beverage_type(con, TOTAL_BEVERAGE_NAME)

    try:
        con.execute("DELETE FROM fact_global_consumption")

        con.execute(
            f"""
            INSERT INTO fact_global_consumption
                (id, country_id, year_id, beverage_type_id,
                 liters_pure_alcohol_pc, pct_drinkers, sex)
            SELECT
                ROW_NUMBER() OVER () AS id,
                dc.country_id,
                dy.year_id,
                {beverage_id} AS beverage_type_id,
                f.liters_pure_alcohol_pc,
                f.pct_drinkers,
                f.sex
            FROM read_parquet('{fact_parquet}') AS f
            JOIN dim_country dc ON dc.iso3 = f.iso3
            JOIN dim_year    dy ON dy.year  = f.year
            """
        )
        count = con.execute("SELECT count(*) FROM fact_global_consumption").fetchone()[0]
        logger.info("loader_who.facts.loaded", row_count=count)
    except WarehouseError:
        raise
    except Exception as exc:
        raise WarehouseError(f"Failed to load WHO facts: {exc}") from exc


def load_all_who(con: duckdb.DuckDBPyConnection, cleaned_dir: Path) -> None:
    """Orchestrate WHO data loading: dimensions first, then facts.

    Args:
        con: Open DuckDB connection (must be writable).
        cleaned_dir: Path to the cleaned/who/ directory.

    Raises:
        WarehouseError: If any loading step fails.
    """
    load_who_dimensions(con, cleaned_dir)
    load_who_facts(con, cleaned_dir)
