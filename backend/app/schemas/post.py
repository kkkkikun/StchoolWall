from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class PostCreate(BaseModel):
    post_type: str = Field(..., pattern=r"^(lost_found|second_hand|carpool|general|advertisement)$")
    content: str = Field(..., min_length=1, max_length=2000)
    category: str | None = Field(None, max_length=20)
    images: list[str] = Field(default_factory=list, max_length=6)
    price: float | None = Field(None, ge=0, le=10_000_000)
    tag_ids: list[int] = Field(default_factory=list, max_length=10)

    @field_validator("images")
    @classmethod
    def images_must_be_local_static(cls, v: list[str]) -> list[str]:
        """仅允许本站 /static/ 相对路径：外部 URL 会进入审核管线的服务端取回链路（SSRF）。"""
        for url in v:
            if not url.startswith("/static/") or len(url) > 200:
                raise ValueError("images 仅允许 /static/ 开头的相对路径（≤200 字符）")
        return v


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
    description: str | None = Field(None, max_length=1000)
