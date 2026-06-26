from pydantic import BaseModel, Field


class BoardCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    prefix: str = Field(default="TASK", min_length=1, max_length=10)
    start_number: int = Field(default=1, ge=1)  # the first task's running number
    member_ids: list[str] = []


class BoardUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    prefix: str | None = Field(default=None, min_length=1, max_length=10)
    member_ids: list[str] | None = None
