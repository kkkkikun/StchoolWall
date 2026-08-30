from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator


class BannerCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=50)
    desc: str | None = Field(None, max_length=100)
    tag: str | None = Field(None, max_length=10)
    image_url: str | None = Field(None, max_length=500)
    link_url: str | None = Field(None, max_length=500)
    post_id: int | None = None
    sort: int = 0
    status: int = Field(1, ge=0, le=1)
    start_at: datetime | None = None
    end_at: datetime | None = None

    @field_validator("link_url")
    @classmethod
    def _link_must_be_http(cls, v: str | None) -> str | None:
        if v and not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("link_url 必须以 http:// 或 https:// 开头")
        return v

    @model_validator(mode="after")
    def _target_mutually_exclusive(self) -> "BannerCreate":
        if self.link_url and self.post_id:
            raise ValueError("link_url 与 post_id 只能二选一")
        return self


class BannerUpdate(BaseModel):
    """全字段可选；未提供的字段保持原值。"""

    title: str | None = Field(None, min_length=1, max_length=50)
    desc: str | None = Field(None, max_length=100)
    tag: str | None = Field(None, max_length=10)
    image_url: str | None = Field(None, max_length=500)
    link_url: str | None = Field(None, max_length=500)
    post_id: int | None = None
    sort: int | None = None
    status: int | None = Field(None, ge=0, le=1)
    start_at: datetime | None = None
    end_at: datetime | None = None

    @field_validator("link_url")
    @classmethod
    def _link_must_be_http(cls, v: str | None) -> str | None:
        if v and not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("link_url 必须以 http:// 或 https:// 开头")
        return v

    @model_validator(mode="after")
    def _target_mutually_exclusive(self) -> "BannerUpdate":
        if self.link_url and self.post_id:
            raise ValueError("link_url 与 post_id 只能二选一")
        return self
