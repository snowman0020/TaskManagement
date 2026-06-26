from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class SprintCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    start_date: date
    goal: str = ""
    weeks: int = Field(default=2, ge=1, le=4)  # sprint length in weeks
    manday: float | None = Field(default=None, ge=0)  # planned capacity (man-days)


class SprintGenerate(BaseModel):
    """Auto-generate consecutive sprints starting on a Monday."""
    start_date: date  # must be a Monday (validated server-side)
    count: int = Field(default=6, ge=1, le=52)
    weeks: int = Field(default=2, ge=1, le=4)
    name_prefix: str = "Sprint"
    manday: float | None = Field(default=None, ge=0)  # default applied to all


class SprintUpdate(BaseModel):
    name: str | None = None
    goal: str | None = None
    status: Literal["planned", "active", "completed"] | None = None
    manday: float | None = Field(default=None, ge=0)


class StatusColumnCreate(BaseModel):
    key: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=60)
    order: int = 0
    wip_limit: int | None = None
    is_done: bool = False  # marks the column that completes a task (for leadtime)


class StatusColumnUpdate(BaseModel):
    name: str | None = None
    order: int | None = None
    wip_limit: int | None = None
    is_done: bool | None = None
