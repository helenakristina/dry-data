"""Base class for data transformers.

Transformers read raw files from data/raw/{source}/, clean and normalize
them using Polars, and write Parquet files to data/cleaned/{source}/.
"""

import abc
from pathlib import Path

import polars as pl
import structlog

from dry_data.config import settings

logger = structlog.get_logger()


class BaseTransformer(abc.ABC):
    """Abstract base for all data source transformers."""

    @property
    @abc.abstractmethod
    def source_name(self) -> str:
        """Must match the corresponding ingestor's source_name."""

    @property
    def raw_dir(self) -> Path:
        """Directory containing raw input files."""
        return settings.raw_dir / self.source_name

    @property
    def cleaned_dir(self) -> Path:
        """Directory where cleaned Parquet files are written."""
        path = settings.cleaned_dir / self.source_name
        path.mkdir(parents=True, exist_ok=True)
        return path

    @abc.abstractmethod
    def transform(self) -> list[Path]:
        """Read raw files, clean, and write Parquet outputs.

        Returns:
            List of paths to Parquet files in self.cleaned_dir.

        Raises:
            TransformError: If cleaning or validation fails.
        """

    def _write_parquet(self, df: pl.DataFrame, name: str) -> Path:
        """Write a DataFrame to Parquet with consistent settings.

        Args:
            df: The cleaned DataFrame to write.
            name: Filename without extension (e.g., 'fact_brfss_responses').

        Returns:
            Path to the written Parquet file.
        """
        path = self.cleaned_dir / f"{name}.parquet"
        df.write_parquet(path, compression="zstd")
        logger.info(
            "transform.write_parquet",
            source=self.source_name,
            file=name,
            rows=df.height,
            columns=df.width,
        )
        return path

    def run(self) -> list[Path]:
        """Execute the transform pipeline with logging."""
        logger.info("transform.start", source=self.source_name)
        paths = self.transform()
        logger.info(
            "transform.complete",
            source=self.source_name,
            file_count=len(paths),
        )
        return paths
