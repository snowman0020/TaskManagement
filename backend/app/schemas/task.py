from datetime import datetime

from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    status: str | None = None  # defaults to first column
    priority: str = "medium"  # low | medium | high | critical
    assignee_id: str | None = None
    sprint_id: str | None = None
    story_points: int | None = None
    due_date: datetime | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    assignee_id: str | None = None
    sprint_id: str | None = None
    story_points: int | None = None
    due_date: datetime | None = None


class TaskMove(BaseModel):
    """Payload for drag-and-drop reordering."""
    status: str
    order: float


class TaskReorderItem(BaseModel):
    id: str
    status: str
    order: float


class TaskReorder(BaseModel):
    items: list[TaskReorderItem]
