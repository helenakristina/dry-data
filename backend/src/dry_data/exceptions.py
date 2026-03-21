"""Custom exceptions for Dry Data.

Each pipeline stage has its own exception class so callers can catch
at the granularity they need.
"""


class DryDataError(Exception):
    """Base exception for all Dry Data errors."""


class IngestionError(DryDataError):
    """Raised when data download or raw file handling fails."""


class TransformError(DryDataError):
    """Raised when data cleaning or transformation fails."""


class WarehouseError(DryDataError):
    """Raised when DuckDB schema or loading operations fail."""


class QueryError(DryDataError):
    """Raised when a user query cannot be executed safely."""


class LLMError(DryDataError):
    """Raised when the LLM API call fails or returns unusable output."""
