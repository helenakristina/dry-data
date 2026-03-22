"""Datasets listing route."""

from fastapi import APIRouter, Depends

from dry_data.api.dependencies import get_base_data_repo
from dry_data.models.api import DatasetInfo
from dry_data.warehouse.repository_base import BaseDataRepository

router = APIRouter()


@router.get("/datasets", response_model=list[DatasetInfo])
async def list_datasets(
    repo: BaseDataRepository = Depends(get_base_data_repo),
) -> list[DatasetInfo]:
    """Return metadata for all available datasets."""
    return repo.list_tables()
