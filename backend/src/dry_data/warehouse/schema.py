"""DuckDB star schema definitions for Dry Data.

This module contains all CREATE TABLE statements. The schema follows a star
schema pattern: fact tables hold measurements with foreign keys pointing to
shared dimension tables.
"""

DIMENSION_TABLES = {
    "dim_state": """
        CREATE TABLE IF NOT EXISTS dim_state (
            state_id    INTEGER PRIMARY KEY,
            state_fips  VARCHAR(2) NOT NULL,
            state_abbr  VARCHAR(2) NOT NULL,
            state_name  VARCHAR(50) NOT NULL,
            region      VARCHAR(20) NOT NULL,
            division    VARCHAR(30) NOT NULL
        );
    """,
    "dim_country": """
        CREATE TABLE IF NOT EXISTS dim_country (
            country_id   INTEGER PRIMARY KEY,
            iso3         VARCHAR(3) NOT NULL,
            iso2         VARCHAR(2),
            country_name VARCHAR(100) NOT NULL,
            continent    VARCHAR(20),
            who_region   VARCHAR(50)
        );
    """,
    "dim_year": """
        CREATE TABLE IF NOT EXISTS dim_year (
            year_id INTEGER PRIMARY KEY,
            year    INTEGER NOT NULL UNIQUE
        );
    """,
    "dim_age_group": """
        CREATE TABLE IF NOT EXISTS dim_age_group (
            age_group_id INTEGER PRIMARY KEY,
            age_label    VARCHAR(20) NOT NULL,
            age_min      INTEGER,
            age_max      INTEGER
        );
    """,
    "dim_beverage_type": """
        CREATE TABLE IF NOT EXISTS dim_beverage_type (
            beverage_type_id INTEGER PRIMARY KEY,
            beverage_name    VARCHAR(30) NOT NULL
        );
    """,
}

FACT_TABLES = {
    "fact_brfss_responses": """
        CREATE TABLE IF NOT EXISTS fact_brfss_responses (
            response_id         INTEGER PRIMARY KEY,
            year_id             INTEGER REFERENCES dim_year(year_id),
            state_id            INTEGER REFERENCES dim_state(state_id),
            age_group_id        INTEGER REFERENCES dim_age_group(age_group_id),
            sex                 VARCHAR(1),
            drink_days_30d      INTEGER,
            avg_drinks_occasion FLOAT,
            binge_episodes_30d  INTEGER,
            heavy_drinker       BOOLEAN,
            sample_weight       FLOAT NOT NULL
        );
    """,
    "fact_global_consumption": """
        CREATE TABLE IF NOT EXISTS fact_global_consumption (
            id                      INTEGER PRIMARY KEY,
            country_id              INTEGER REFERENCES dim_country(country_id),
            year_id                 INTEGER REFERENCES dim_year(year_id),
            beverage_type_id        INTEGER REFERENCES dim_beverage_type(beverage_type_id),
            liters_pure_alcohol_pc  FLOAT,
            pct_drinkers            FLOAT,
            sex                     VARCHAR(10)
        );
    """,
    "fact_us_spending": """
        CREATE TABLE IF NOT EXISTS fact_us_spending (
            id                      INTEGER PRIMARY KEY,
            year_id                 INTEGER REFERENCES dim_year(year_id),
            avg_annual_expenditure  FLOAT,
            pct_total_expenditure   FLOAT,
            source                  VARCHAR(20)
        );
    """,
    "fact_trend_interest": """
        CREATE TABLE IF NOT EXISTS fact_trend_interest (
            id              INTEGER PRIMARY KEY,
            week_start      DATE NOT NULL,
            keyword         VARCHAR(50) NOT NULL,
            interest_score  INTEGER,
            geo             VARCHAR(5)
        );
    """,
}

ALL_TABLES = {**DIMENSION_TABLES, **FACT_TABLES}


def create_all_tables(con) -> None:  # type: ignore[annotation-unchecked]
    """Execute all CREATE TABLE statements against an open DuckDB connection.

    Args:
        con: An open duckdb connection.
    """
    for _table_name, ddl in DIMENSION_TABLES.items():
        con.execute(ddl)
    for _table_name, ddl in FACT_TABLES.items():
        con.execute(ddl)


def get_table_descriptions() -> dict[str, str]:
    """Return human-readable descriptions for each table.

    Used by the MCP server's list_datasets tool and by the LLM's schema context.
    """
    return {
        "dim_state": "US states with FIPS codes, abbreviations, and Census regions/divisions.",
        "dim_country": "Countries with ISO codes, names, continents, and WHO regions.",
        "dim_year": "Calendar years used as a shared time dimension.",
        "dim_age_group": "Age group brackets used in survey data.",
        "dim_beverage_type": "Beverage categories: beer, wine, spirits, other, total.",
        "fact_brfss_responses": (
            "Individual-level CDC BRFSS survey responses with drinking frequency, "
            "binge drinking episodes, and sample weights. ~450k rows per year."
        ),
        "fact_global_consumption": (
            "Country-level alcohol consumption from WHO/Our World in Data. "
            "Per-capita liters of pure alcohol by beverage type, 190+ countries."
        ),
        "fact_us_spending": (
            "US household alcohol spending from FRED/BLS Consumer Expenditure Survey. "
            "Annual average expenditure and share of total spending, 1984-present."
        ),
        "fact_trend_interest": (
            "Weekly Google Trends interest scores for alcohol-related keywords "
            "(sober curious, dry january, mocktail, etc.)."
        ),
    }
