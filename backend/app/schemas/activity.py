from datetime import datetime

from pydantic import BaseModel, Field


class ActivityCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    image_url: str | None = Field(None, max_length=500)
    summary: str | None = Field(None, max_length=200)
    content: str = Field(..., min_length=1, max_length=5000)
    location: str | None = Field(None, max_length=100)
    start_at: datetime | None = None
    end_at: datetime | None = None
    status: int = Field(1, ge=0, le=1)


class ActivityUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=100)
    image_url: str | None = Field(None, max_length=500)
    summary: str | None = Field(None, max_length=200)
    content: str | None = Field(None, min_length=1, max_length=5000)
    location: str | None = Field(None, max_length=100)
    start_at: datetime | None = None
    end_at: datetime | None = None
    status: int | None = Field(None, ge=0, le=1)
