import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from fastapi import UploadFile

from app.config import settings

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


class StorageBackend(ABC):
    @abstractmethod
    async def get_upload_config(self, filename: str, content_type: str) -> dict:
        """Return upload config dict: {provider, method, upload_url, form_data, public_url}"""

    async def save_upload(self, file: UploadFile, path: str) -> str:
        raise NotImplementedError


class LocalStorage(StorageBackend):
    def __init__(self):
        self.base_dir = Path("static")
        self.base_url = "/static"

    def _generate_path(self, filename: str) -> str:
        ext = Path(filename).suffix.lower()
        now = datetime.now()
        unique_name = f"{uuid.uuid4().hex}{ext}"
        return f"posts/{now.year}/{unique_name}"

    async def get_upload_config(self, filename: str, content_type: str) -> dict:
        path = self._generate_path(filename)
        return {
            "provider": "local",
            "method": "POST",
            "upload_url": "/api/v1/upload/direct",
            "form_data": {"path": path},
            "public_url": f"{self.base_url}/{path}",
        }

    async def save_upload(self, file: UploadFile, path: str) -> str:
        full_path = self.base_dir / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        content = await file.read()
        full_path.write_bytes(content)
        return f"{self.base_url}/{path}"


class R2Storage(StorageBackend):
    def __init__(self):
        self.account_id = settings.CF_R2_ACCOUNT_ID
        self.access_key = settings.CF_R2_ACCESS_KEY
        self.secret_key = settings.CF_R2_SECRET_KEY
        self.bucket = settings.CF_R2_BUCKET
        self.public_url = settings.CF_R2_PUBLIC_URL.rstrip("/")

    def _generate_key(self, filename: str) -> str:
        ext = Path(filename).suffix.lower()
        now = datetime.now()
        unique_name = f"{uuid.uuid4().hex}{ext}"
        return f"posts/{now.year}/{unique_name}"

    async def get_upload_config(self, filename: str, content_type: str) -> dict:
        import boto3
        from botocore.config import Config as BotoConfig

        endpoint = f"https://{self.account_id}.r2.cloudflarestorage.com"
        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=BotoConfig(signature_version="s3v4"),
            region_name="auto",
        )

        key = self._generate_key(filename)
        presigned_url = client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=3600,
        )

        return {
            "provider": "r2",
            "method": "PUT",
            "upload_url": presigned_url,
            "form_data": None,
            "public_url": f"{self.public_url}/{key}",
        }


def get_storage_backend() -> StorageBackend:
    provider = settings.STORAGE_PROVIDER
    if provider == "r2":
        return R2Storage()
    if provider == "aliyun":
        raise NotImplementedError("Aliyun OSS 存储尚未实现")
    return LocalStorage()


def validate_file(filename: str, content_type: str) -> str | None:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return f"不支持的文件类型: {ext}"
    if not content_type.startswith("image/"):
        return f"仅支持图片文件，收到: {content_type}"
    return None
