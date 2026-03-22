"""WHO-specific data repository.

Extends BaseDataRepository with pre-built analytical queries for
the WHO/OWID alcohol consumption dataset.
"""

import duckdb
import structlog

from dry_data.models.llm import PlotlySpec
from dry_data.warehouse.repository_base import BaseDataRepository

logger = structlog.get_logger()


class WHORepository(BaseDataRepository):
    """Repository for WHO global alcohol consumption data."""

    def __init__(self, con: duckdb.DuckDBPyConnection) -> None:
        super().__init__(con)

    def get_global_trend_chart(self) -> PlotlySpec:
        """Return a Plotly line chart of global average alcohol consumption over time.

        Aggregates total-sex rows from fact_global_consumption, computes the
        mean liters_pure_alcohol_pc per year across all countries, and returns
        a single line trace.

        Returns:
            PlotlySpec with one line trace (x=years, y=avg liters), or an
            empty PlotlySpec if the fact table has no total-sex rows.
        """
        rows = self._con.execute(
            """
            SELECT dy.year, AVG(f.liters_pure_alcohol_pc) AS avg_liters
            FROM fact_global_consumption f
            JOIN dim_year dy ON dy.year_id = f.year_id
            WHERE f.sex = 'total'
              AND f.liters_pure_alcohol_pc IS NOT NULL
            GROUP BY dy.year
            ORDER BY dy.year
            """
        ).fetchall()

        if not rows:
            logger.info("repository_who.global_trend.empty")
            return PlotlySpec(data=[])

        years = [row[0] for row in rows]
        avg_liters = [round(row[1], 2) for row in rows]

        trace = {
            "type": "scatter",
            "mode": "lines+markers",
            "name": "Global average",
            "x": years,
            "y": avg_liters,
        }
        layout = {
            "title": "Global Alcohol Consumption (liters pure alcohol per capita)",
            "xaxis": {"title": "Year"},
            "yaxis": {"title": "Liters per capita"},
        }
        logger.info("repository_who.global_trend.built", years=len(years))
        return PlotlySpec(data=[trace], layout=layout)
