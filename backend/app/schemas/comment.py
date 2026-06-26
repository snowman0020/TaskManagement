from pydantic import BaseModel, Field


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    parent_id: str | None = None  # set to a top-level comment id to reply
