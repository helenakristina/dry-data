"""Base data repository for safe DuckDB query execution.

Enforces read-only access and row limits for all queries.
"""

import re

import duckdb
import structlog

from dry_data.exceptions import QueryError
from dry_data.models.api import DatasetInfo
from dry_data.models.warehouse import ColumnInfo, QueryResult, TableSchema
from dry_data.warehouse.schema import get_table_descriptions

logger = structlog.get_logger()

_FORBIDDEN_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|ATTACH|COPY|EXPORT|IMPORT"
    r"|TRUNCATE|PRAGMA|SET|CALL|LOAD|INSTALL|VACUUM)\b",
    re.IGNORECASE,
)


class BaseDataRepository:
    """Read-only DuckDB repository with SQL safety enforcement."""

    def __init__(self, con: duckdb.DuckDBPyConnection) -> None:
        self._con = con

    def _validate_sql(self, sql: str) -> None:
        """Raise QueryError if sql contains prohibited statements.

        Args:
            sql: The SQL string to validate.

        Raises:
            QueryError: If sql contains a prohibited keyword.
        """
        if _FORBIDDEN_PATTERN.search(sql):
            raise QueryError(f"Prohibited SQL statement: {sql!r}")

    def execute_safe_query(self, sql: str, max_rows: int = 1000) -> QueryResult:
        """Execute a read-only SQL query and return results.

        Args:
            sql: The SQL query to execute.
            max_rows: Maximum number of rows to return.

        Returns:
            QueryResult with columns and rows (rows are lists, not tuples).

        Raises:
            QueryError: If sql is prohibited or execution fails.
        """
        self._validate_sql(sql)
        try:
            relation = self._con.execute(sql)
            columns = [desc[0] for desc in relation.description]
            rows = [list(row) for row in relation.fetchmany(max_rows)]
            logger.info("repository.query.executed", row_count=len(rows))
            return QueryResult(columns=columns, rows=rows)
        except QueryError:
            raise
        except Exception as exc:
            raise QueryError(f"Query failed: {exc}") from exc

    def get_table_schema(self, table_name: str) -> TableSchema:
        """Return schema metadata for a table.

        Args:
            table_name: Name of the table to inspect.

        Returns:
            TableSchema with column names, types, and row count.

        Raises:
            QueryError: If the table does not exist.
        """
        try:
            cols_result = self._con.execute(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_name = ? "
                "ORDER BY ordinal_position",
                [table_name],
            ).fetchall()
        except Exception as exc:
            raise QueryError(f"Failed to get schema for {table_name!r}: {exc}") from exc

        if not cols_result:
            raise QueryError(f"Table not found: {table_name!r}")

        columns = [
            ColumnInfo(
                name=row[0],
                type=row[1],
                nullable=(row[2].upper() == "YES"),
                sample_values=[],
            )
            for row in cols_result
        ]

        # Use double-quote identifier escaping — SQL identifiers cannot be parameterized
        # via ? placeholders, so we escape embedded quotes and wrap in double quotes.
        safe_name = '"' + table_name.replace('"', '""') + '"'
        try:
            row_count = self._con.execute(
                f"SELECT COUNT(*) FROM {safe_name}"
            ).fetchone()[0]
        except Exception as exc:
            raise QueryError(f"Failed to count rows in {table_name!r}: {exc}") from exc

        return TableSchema(table_name=table_name, columns=columns, row_count=row_count)

    def list_tables(self) -> list[DatasetInfo]:
        """Return a DatasetInfo list for all known tables.

        Returns:
            List of DatasetInfo objects for each table with a description.
        """
        descriptions = get_table_descriptions()
        datasets: list[DatasetInfo] = []
        for table_name, description in descriptions.items():
            try:
                schema = self.get_table_schema(table_name)
                datasets.append(
                    DatasetInfo(
                        table_name=table_name,
                        description=description,
                        row_count=schema.row_count,
                        columns=schema.columns,
                    )
                )
            except QueryError:
                logger.warning("repository.list_tables.missing", table_name=table_name)
        return datasets
