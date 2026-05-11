from pydantic import BaseModel, Field


class ProfileResponse(BaseModel):
    nickname: str
    real_name: str | None = None
    student_id: str | None = None
    wechat_id: str | None = None

    model_config = {"from_attributes": True}


class ProfileUpdateRequest(BaseModel):
    nickname: str | None = Field(None, min_length=1, max_length=50)
    wechat_id: str | None = Field(None, max_length=50)
