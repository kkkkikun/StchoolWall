from datetime import datetime

from pydantic import BaseModel, Field


class PostCreate(BaseModel):
    post_type: str = Field(..., pattern=r"^(lost_found|second_hand|carpool|general|advertisement)$")
    content: str = Field(..., min_length=1, max_length=2000)
    category: str | None = Field(None, max_length=20)
    images: list[str] = Field(default_factory=list, max_length=6)
    price: float | None = Field(None, ge=0)
    tag_ids: list[int] = Field(default_factory=list)


class PostBrief(BaseModel):
    id: int
    post_type: str
    content: str
    images: list[str]
    price: float | None
    status: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PostListResponse(BaseModel):
    items: list[PostBrief]
    next_cursor: int | None
    has_more: bool


class ReportRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
