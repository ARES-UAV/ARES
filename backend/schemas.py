"""Pydantic models for anything crossing the API boundary.

`Detection` mirrors the perception data contract in CLAUDE.md exactly. That
format is agreed across detection, tracking, localization and the dashboard —
it must not be changed unilaterally.
"""

from typing import List

from pydantic import BaseModel, Field


class Detection(BaseModel):
    """One detected person in one frame."""

    frame_id: int = Field(..., ge=0, description="Zero-indexed frame number")
    bbox: List[float] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="[x1, y1, x2, y2] in source-resolution pixels",
    )
    confidence: float = Field(..., ge=0.0, le=1.0)
    track_id: int = Field(..., description="Persistent per-person ID; -1 = untracked")
    class_id: int = Field(0, alias="class", description="0 = person")

    model_config = {"populate_by_name": True}


class Health(BaseModel):
    """Liveness response for the dashboard's connection indicator."""

    status: str
    service: str
    version: str
