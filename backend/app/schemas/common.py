from pydantic import BaseModel


class ResponseBase(BaseModel):
    code: int = 0
    message: str = "success"
