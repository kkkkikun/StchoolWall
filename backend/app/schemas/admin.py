from pydantic import BaseModel, Field


class ReportHandle(BaseModel):
    action: str = Field(..., pattern="^(dismiss|ban_post|ban_user)$")
