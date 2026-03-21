"""Base class for data ingestors.

Every data source (BRFSS, WHO, FRED, Trends) implements this interface.
Ingestors are responsible for downloading raw data to data/raw/{source_name}/
and are idempotent — running twice produces the same result.
"""

import abc
from pathlib import Path

import structlog

from dry_data.config import settings

logger = structlog.get_logger()


class BaseIngestor(abc.ABC):
    """Abstract base for all data source ingestors."""

    @property
    @abc.abstractmethod
    def source_name(self) -> str:
        """Short identifier used in directory names and logs.

        Examples: 'brfss', 'who', 'fred', 'trends'.
        """

    @property
    def raw_dir(self) -> Path:
        """Directory where this source's raw files are stored."""
        path = settings.raw_dir / self.source_name
        path.mkdir(parents=True, exist_ok=True)
        return path

    @abc.abstractmethod
    def download(self) -> list[Path]:
        """Download raw data files and return their paths.

        Returns:
            List of paths to downloaded files in self.raw_dir.

        Raises:
            IngestionError: If download fails after retries.
        """

    def run(self) -> list[Path]:
        """Execute the ingestion pipeline with logging."""
        logger.info("ingest.start", source=self.source_name)
        paths = self.download()
        logger.info(
            "ingest.complete",
            source=self.source_name,
            file_count=len(paths),
            files=[str(p.name) for p in paths],
        )
        return paths
