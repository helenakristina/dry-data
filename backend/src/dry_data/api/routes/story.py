"""Story / pre-built chart routes."""

from fastapi import APIRouter, Depends

from dry_data.api.dependencies import get_who_repo
from dry_data.models.llm import PlotlySpec
from dry_data.warehouse.repository_who import WHORepository

router = APIRouter()


@router.get("/story/global-trend", response_model=PlotlySpec)
async def global_trend(
    repo: WHORepository = Depends(get_who_repo),
) -> PlotlySpec:
    """Return a Plotly line chart of global average alcohol consumption over time."""
    return repo.get_global_trend_chart()
