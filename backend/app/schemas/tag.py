from pydantic import BaseModel, Field


class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=30)


class TagResponse(BaseModel):
    id: int
    name: str
