"""互动模块请求/响应 schema。响应沿用既有风格（router 返回 {code, data} dict）。"""
from pydantic import BaseModel, Field


class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)
