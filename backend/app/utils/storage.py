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
        self.base_dir = Path(settings.STATIC_BASE_DIR)
        self.base_url = "/static"

    def _safe_path(self, path: str) -> Path:
        """拼接并校验路径，防 ../ 穿越与同前缀兄弟目录逃逸（路径包含语义，非字符串前缀）。"""
        full = (self.base_dir / path).resolve()
        base = self.base_dir.resolve()
        if not full.is_relative_to(base):
            raise ValueError("非法路径")
        return full

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
        full_path = self._safe_path(path)
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

# Private media storage has no StaticFiles mount and never accepts caller-chosen paths.
def _private_key(key: str) -> str:
    import re
    if not re.fullmatch(r"quarantine/[0-9a-f]{32}\.jpg", key):
        raise ValueError("非法媒体存储标识")
    return key


def _private_path(key: str) -> Path:
    configured = Path(getattr(settings, "PRIVATE_MEDIA_DIR", "private-media"))
    static = Path(settings.STATIC_BASE_DIR).resolve()
    base = configured.resolve() if configured.is_absolute() else (static.parent / configured).resolve()
    if base.is_relative_to(static):
        raise ValueError("私有媒体目录不能位于公开静态目录内")
    path = (base / _private_key(key)).resolve()
    if not path.is_relative_to(base):
        raise ValueError("非法媒体路径")
    return path


def _cos_client():
    from qcloud_cos import CosConfig, CosS3Client
    options = dict(Region=settings.COS_REGION, SecretId=settings.COS_SECRET_ID,
                   SecretKey=settings.COS_SECRET_KEY, Scheme="https")
    endpoint = getattr(settings, "COS_ENDPOINT", "")
    if endpoint:
        options["Endpoint"] = endpoint
    return CosS3Client(CosConfig(**options))


async def write_private_media(key: str, content: bytes) -> None:
    import asyncio
    key = _private_key(key)
    if len(content) > MAX_FILE_SIZE:
        raise ValueError("图片超过大小限制")
    if settings.STORAGE_PROVIDER == "cos":
        await asyncio.to_thread(_cos_client().put_object, Bucket=settings.COS_BUCKET,
                                Key=key, Body=content, ContentType="image/jpeg",
                                ACL="private")
        return
    if settings.STORAGE_PROVIDER != "local":
        raise ValueError("隔离媒体存储仅支持 local 或 cos")
    def save():
        path = _private_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(content)
    await asyncio.to_thread(save)


async def read_private_media(key: str) -> bytes:
    import asyncio
    key = _private_key(key)
    def read():
        if settings.STORAGE_PROVIDER == "cos":
            result = _cos_client().get_object(Bucket=settings.COS_BUCKET, Key=key)
            stream = result["Body"].get_raw_stream()
            try:
                return stream.read(MAX_FILE_SIZE + 1)
            finally:
                stream.close()
        if settings.STORAGE_PROVIDER != "local":
            raise ValueError("隔离媒体存储仅支持 local 或 cos")
        path = _private_path(key)
        if path.stat().st_size > MAX_FILE_SIZE:
            raise ValueError("图片超过大小限制")
        with path.open("rb") as handle:
            return handle.read(MAX_FILE_SIZE + 1)
    data = await asyncio.to_thread(read)
    if len(data) > MAX_FILE_SIZE:
        raise ValueError("图片超过大小限制")
    return data


async def delete_private_media(key: str) -> None:
    import asyncio
    key = _private_key(key)
    if settings.STORAGE_PROVIDER == "cos":
        await asyncio.to_thread(_cos_client().delete_object, Bucket=settings.COS_BUCKET, Key=key)
        return
    if settings.STORAGE_PROVIDER != "local":
        raise ValueError("隔离媒体存储仅支持 local 或 cos")
    await asyncio.to_thread(_private_path(key).unlink, missing_ok=True)


async def old_private_media_keys(cutoff, limit: int = 5000) -> list[str]:
    """Find aged unreferenced candidates; the service confirms absence from the DB."""
    import asyncio
    import re
    from datetime import datetime, timezone
    def scan():
        found = []
        if settings.STORAGE_PROVIDER == "cos":
            client, marker = _cos_client(), ""
            for _ in range(5):
                page = client.list_objects(Bucket=settings.COS_BUCKET, Prefix="quarantine/",
                                           Marker=marker, MaxKeys=1000)
                for item in page.get("Contents", []):
                    key = item.get("Key", "")
                    if not re.fullmatch(r"quarantine/[0-9a-f]{32}\.jpg", key):
                        continue
                    modified = datetime.fromisoformat(item["LastModified"].replace("Z", "+00:00"))
                    if modified < cutoff:
                        found.append(key)
                if str(page.get("IsTruncated", "false")).lower() != "true":
                    break
                next_marker = page.get("NextMarker")
                if not next_marker or next_marker == marker:
                    break
                marker = next_marker
            return found[:limit]
        if settings.STORAGE_PROVIDER != "local":
            return []
        directory = _private_path("quarantine/" + "0" * 32 + ".jpg").parent
        if not directory.exists():
            return []
        for path in directory.iterdir():
            if len(found) >= limit:
                break
            if re.fullmatch(r"[0-9a-f]{32}\.jpg", path.name) and path.is_file():
                if datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) < cutoff:
                    found.append("quarantine/" + path.name)
        return found
    return await asyncio.to_thread(scan)
