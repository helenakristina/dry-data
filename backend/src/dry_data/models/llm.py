"""LLM-related Pydantic models."""

from pydantic import BaseModel


class PlotlySpec(BaseModel):
    """A Plotly figure specification returned by the LLM or pre-built queries.

    The frontend passes this directly to react-plotly.js via ChartRenderer.
    """

    data: list[dict]
    layout: dict | None = None
