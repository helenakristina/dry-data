"""WHO/OWID alcohol consumption data ingestor.

Downloads three CSV files from Our World in Data (CC BY 4.0):
  - Total per-capita consumption
  - Consumption by sex (male/female)
  - Share of adults who drink alcohol
"""

from pathlib import Path

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from dry_data.exceptions import IngestionError
from dry_data.ingest.base import BaseIngestor

logger = structlog.get_logger()

OWID_BASE = "https://ourworldindata.org/grapher"
CSV_PARAMS = "?v=1&csvType=full&useColumnShortNames=false"

SOURCES: list[tuple[str, str]] = [
    (
        f"{OWID_BASE}/total-alcohol-consumption-per-capita-litres-of-pure-alcohol.csv{CSV_PARAMS}",
        "consumption.csv",
    ),
    (
        f"{OWID_BASE}/alcohol-consumption-per-capita-men-women.csv{CSV_PARAMS}",
        "consumption_by_sex.csv",
    ),
    (
        f"{OWID_BASE}/share-of-adults-who-drink-alcohol.csv{CSV_PARAMS}",
        "share_drinkers.csv",
    ),
]


class WHOIngestor(BaseIngestor):
    """Downloads WHO/OWID alcohol consumption CSVs."""

    # Injected in tests to avoid touching the real raw_dir
    _raw_dir_override: Path | None = None

    @property
    def source_name(self) -> str:
        """Identifier used for directory names and logs."""
        return "who"

    @property
    def raw_dir(self) -> Path:
        if self._raw_dir_override is not None:
            return self._raw_dir_override
        return super().raw_dir

    def download(self) -> list[Path]:
        """Download the three OWID CSVs.

        Returns:
            List of paths to the downloaded CSV files.

        Raises:
            IngestionError: If any download fails or returns empty content.
        """
        paths: list[Path] = []
        for url, filename in SOURCES:
            path = self._download_one(url, filename)
            paths.append(path)
        return paths

    def _download_one(self, url: str, filename: str) -> Path:
        """Download a single CSV and write it to raw_dir.

        Args:
            url: Full URL to download.
            filename: Target filename in raw_dir.

        Returns:
            Path to the downloaded file.

        Raises:
            IngestionError: On HTTP error, network failure, or empty response.
        """
        try:
            content = self._fetch(url)
        except httpx.RequestError as exc:
            raise IngestionError(f"Network error downloading {filename}: {exc}") from exc

        if not content:
            raise IngestionError(f"Empty response downloading {filename} from {url}")

        dest = self.raw_dir / filename
        dest.write_bytes(content)
        logger.info("ingest.who.saved", filename=filename, bytes=len(content))
        return dest

    @retry(
        retry=retry_if_exception_type(httpx.RequestError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def _fetch(self, url: str) -> bytes:
        """Fetch URL bytes, retrying only on transient network errors.

        Args:
            url: The URL to fetch.

        Returns:
            Raw response bytes.

        Raises:
            IngestionError: On HTTP status errors (no retry).
            httpx.RequestError: On transient network errors (retried).
        """
        logger.info("ingest.who.fetching", url=url)
        try:
            response = httpx.get(url, follow_redirects=True, timeout=60)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise IngestionError(
                f"HTTP {exc.response.status_code} fetching {url}"
            ) from exc
        return response.content
