"""Tests for the WHO ingestor.

Uses pytest-httpx to mock all HTTP calls — never hits real OWID URLs.
"""

import pytest
from pytest_httpx import HTTPXMock

from dry_data.exceptions import IngestionError
from dry_data.ingest.who import WHOIngestor

SAMPLE_CSV = b"Entity,Code,Year,total_alcohol\nFrance,FRA,2020,12.1\nGermany,DEU,2020,11.4\n"
SAMPLE_CONSUMPTION_BY_SEX_CSV = (
    b"Entity,Code,Year,male_alcohol,female_alcohol\nFrance,FRA,2020,18.0,6.2\n"
)
SAMPLE_SHARE_DRINKERS_CSV = b"Entity,Code,Year,share_drinkers\nFrance,FRA,2020,0.72\n"


# CATCHES: Ingestor silently returns empty list when the remote server returns
#          a 4xx instead of raising IngestionError
def test_who_ingestor_raises_on_http_error(tmp_path, httpx_mock: HTTPXMock):
    httpx_mock.add_response(status_code=403)
    ingestor = WHOIngestor()
    ingestor._raw_dir_override = tmp_path
    with pytest.raises(IngestionError, match="403"):
        ingestor.download()


# CATCHES: Downloaded file is empty (0 bytes) but ingestor reports success,
#          causing the transformer to crash later with a cryptic Polars error
def test_who_ingestor_rejects_empty_response(tmp_path, httpx_mock: HTTPXMock):
    httpx_mock.add_response(content=b"")
    ingestor = WHOIngestor()
    ingestor._raw_dir_override = tmp_path
    with pytest.raises(IngestionError, match=r"[Ee]mpty"):
        ingestor.download()


# CATCHES: Ingestor writes files with wrong names, breaking the transformer's
#          hardcoded path expectations
def test_who_ingestor_writes_correct_filenames(tmp_path, httpx_mock: HTTPXMock):
    httpx_mock.add_response(content=SAMPLE_CSV)
    httpx_mock.add_response(content=SAMPLE_CONSUMPTION_BY_SEX_CSV)
    httpx_mock.add_response(content=SAMPLE_SHARE_DRINKERS_CSV)
    ingestor = WHOIngestor()
    ingestor._raw_dir_override = tmp_path
    paths = ingestor.download()
    filenames = {p.name for p in paths}
    assert filenames == {"consumption.csv", "consumption_by_sex.csv", "share_drinkers.csv"}


# CATCHES: Running ingestor twice creates duplicate/appended files rather than
#          overwriting, doubling row counts in downstream transforms
def test_who_ingestor_is_idempotent(tmp_path, httpx_mock: HTTPXMock):
    for _ in range(6):  # 3 files x 2 runs
        httpx_mock.add_response(content=SAMPLE_CSV)
    ingestor = WHOIngestor()
    ingestor._raw_dir_override = tmp_path
    ingestor.download()
    ingestor.download()
    assert len(list(tmp_path.iterdir())) == 3  # not 6
