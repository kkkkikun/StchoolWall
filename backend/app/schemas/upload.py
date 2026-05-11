from pydantic import BaseModel


class UploadConfigData(BaseModel):
    provider: str
    method: str
    upload_url: str
    form_data: dict | None = None
    public_url: str


class DirectUploadResponse(BaseModel):
    public_url: str
