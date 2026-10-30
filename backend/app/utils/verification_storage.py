"""Private evidence storage. There are deliberately no public URLs or upload tickets."""
import asyncio
import io
import json
import re
import warnings
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import settings

MAX_PROOF_BYTES = 5 * 1024 * 1024
MAX_PROOF_PIXELS = 12_000_000
_PROOF_IMAGE_DECODE_LIMIT = asyncio.Semaphore(1)


def sanitize_proof_image(content: bytes) -> bytes:
    if not content or len(content) > MAX_PROOF_BYTES:
        raise HTTPException(400, "照片不得超过 5 MB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError("unsupported format")
                if image.width * image.height > MAX_PROOF_PIXELS or min(image.size) < 200:
                    raise ValueError("invalid dimensions")
                image.load()
                output = io.BytesIO()
                ImageOps.exif_transpose(image).convert("RGB").save(
                    output, format="JPEG", quality=90, optimize=True
                )
                result = output.getvalue()
                if len(result) > MAX_PROOF_BYTES:
                    raise ValueError('encoded image too large')
                return result
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise HTTPException(400, "请上传清晰的 JPG、PNG 或 WebP 照片") from exc


async def read_proof(file: UploadFile) -> bytes:
    content = await file.read(MAX_PROOF_BYTES + 1)
    async with _PROOF_IMAGE_DECODE_LIMIT:
        return await asyncio.to_thread(sanitize_proof_image, content)


class VerificationStorage:
    def __init__(self):
        self.provider = settings.VERIFICATION_STORAGE_PROVIDER
        self.base = Path(settings.VERIFICATION_PRIVATE_DIR).resolve()
        public = Path(settings.STATIC_BASE_DIR).resolve()
        if self.base.is_relative_to(public):
            raise RuntimeError("认证照片目录不得位于公共静态目录")
        if self.provider == "local" and settings.ENVIRONMENT == "production":
            raise RuntimeError("生产认证照片必须使用独立私有 COS 桶")
        if self.provider not in {"local", "cos"}:
            raise RuntimeError("未知认证照片存储类型")

    def _path(self, key: str) -> Path:
        path = (self.base / key).resolve()
        if not path.is_relative_to(self.base):
            raise ValueError("invalid private evidence key")
        return path

    def _cos(self, validate=True):
        import boto3
        from botocore.config import Config
        if not settings.VERIFICATION_COS_BUCKET:
            raise RuntimeError("未配置认证照片私有桶")
        client = boto3.client(
            "s3", endpoint_url=settings.COS_ENDPOINT or
            f"https://cos.{settings.COS_REGION}.myqcloud.com",
            region_name=settings.COS_REGION,
            aws_access_key_id=settings.COS_SECRET_ID,
            aws_secret_access_key=settings.COS_SECRET_KEY,
            config=Config(signature_version="s3v4", connect_timeout=5, read_timeout=10),
        )
        if validate:
            self._validate_cos_privacy(client)
        return client

    def _validate_cos_privacy(self, client):
        from botocore.exceptions import ClientError
        bucket = settings.VERIFICATION_COS_BUCKET
        acl = client.get_bucket_acl(Bucket=bucket)
        if any("AllUsers" in grant.get("Grantee", {}).get("URI", "") or
               "AuthenticatedUsers" in grant.get("Grantee", {}).get("URI", "")
               for grant in acl.get("Grants", [])):
            raise RuntimeError("认证照片桶禁止公开读取")
        try:
            policy = json.loads(client.get_bucket_policy(Bucket=bucket)["Policy"])
            statements = policy.get("Statement", [])
            if isinstance(statements, dict):
                statements = [statements]
            for statement in statements:
                principal = statement.get("Principal")
                values = principal.values() if isinstance(principal, dict) else [principal]
                if statement.get("Effect") == "Allow" and any(
                    value == "*" or isinstance(value, list) and "*" in value for value in values
                ):
                    raise RuntimeError("认证照片桶禁止公共访问策略")
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") not in {"NoSuchBucketPolicy", "404"}:
                raise
        if client.get_bucket_versioning(Bucket=bucket).get("Status") == "Enabled":
            raise RuntimeError("认证照片桶必须关闭版本备份")
        try:
            replication = client.get_bucket_replication(Bucket=bucket)
            if any(rule.get("Status") == "Enabled" for rule in
                   replication.get("ReplicationConfiguration", {}).get("Rules", [])):
                raise RuntimeError("认证照片桶禁止跨桶复制或备份")
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") not in {
                "ReplicationConfigurationNotFoundError", "NoSuchReplicationConfiguration", "404",
            }:
                raise

    @staticmethod
    def _is_evidence_key(key: str) -> bool:
        return bool(re.fullmatch(r"evidence/[0-9a-f-]{36}/[0-9a-f]{32}\.jpg", key))

    def _delete_cos_versions(self, client, key: str) -> None:
        if not self._is_evidence_key(key):
            raise ValueError("invalid private evidence key")
        bucket = settings.VERIFICATION_COS_BUCKET
        # Prefix is insufficient: another object's name can start with this full key.
        objects = []
        for page in client.get_paginator("list_object_versions").paginate(Bucket=bucket, Prefix=key):
            objects.extend({"Key": entry["Key"], "VersionId": entry["VersionId"]}
                           for field in ("Versions", "DeleteMarkers") for entry in page.get(field, [])
                           if entry["Key"] == key)
        for offset in range(0, len(objects), 1000):
            result = client.delete_objects(Bucket=bucket,
                Delete={"Objects": objects[offset:offset + 1000], "Quiet": True})
            if result.get("Errors"):
                raise RuntimeError("私有认证照片版本删除未完成")
        # A never-versioned bucket may omit an unversioned object from the version listing.
        # Never issue a plain delete in enabled/suspended buckets: it could create a new marker.
        if not client.get_bucket_versioning(Bucket=bucket).get("Status"):
            client.delete_object(Bucket=bucket, Key=key)

    async def save(self, key: str, content: bytes) -> None:
        def write():
            if self.provider == "cos":
                self._cos().put_object(
                    Bucket=settings.VERIFICATION_COS_BUCKET, Key=key, Body=content,
                    ContentType="image/jpeg", ACL="private", ServerSideEncryption="AES256",
                )
            else:
                path = self._path(key)
                path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                path.write_bytes(content)
                path.chmod(0o600)
        await asyncio.to_thread(write)

    async def read(self, key: str) -> bytes:
        def read():
            if self.provider == "cos":
                body = self._cos().get_object(
                    Bucket=settings.VERIFICATION_COS_BUCKET, Key=key
                )["Body"]
                try:
                    return body.read(MAX_PROOF_BYTES + 1)
                finally:
                    body.close()
            return self._path(key).read_bytes()
        try:
            content = await asyncio.to_thread(read)
        except FileNotFoundError as exc:
            raise HTTPException(404, "认证照片已删除") from exc
        except Exception as exc:
            from botocore.exceptions import ClientError
            if isinstance(exc, ClientError) and exc.response.get("Error", {}).get("Code") in {
                "NoSuchKey", "NoSuchVersion", "NotFound", "404",
            }:
                raise HTTPException(404, "认证照片已删除") from exc
            raise
        if len(content) > MAX_PROOF_BYTES:
            raise RuntimeError("invalid evidence object")
        return content

    async def delete(self, key: str) -> None:
        def delete():
            if self.provider == "cos":
                self._delete_cos_versions(self._cos(validate=False), key)
            else:
                self._path(key).unlink(missing_ok=True)
        await asyncio.to_thread(delete)

    async def cleanup_orphans(self, active_keys: set[str], before: datetime, limit: int = 200) -> int:
        def candidates():
            if self.provider == "cos":
                newest = {}
                client = self._cos(validate=False)
                for page in client.get_paginator("list_object_versions").paginate(
                    Bucket=settings.VERIFICATION_COS_BUCKET, Prefix="evidence/",
                ):
                    for field in ("Versions", "DeleteMarkers"):
                        for entry in page.get(field, []):
                            key = entry["Key"]
                            if self._is_evidence_key(key):
                                newest[key] = max(newest.get(key, entry["LastModified"]), entry["LastModified"])
                # Include never-versioned objects even when the provider's versions API omits them.
                for page in client.get_paginator("list_objects_v2").paginate(
                    Bucket=settings.VERIFICATION_COS_BUCKET, Prefix="evidence/",
                ):
                    for entry in page.get("Contents", []):
                        key = entry["Key"]
                        if self._is_evidence_key(key):
                            newest[key] = max(newest.get(key, entry["LastModified"]), entry["LastModified"])
                return [key for key, modified in newest.items()
                        if key not in active_keys and modified < before][:limit]
            if not self.base.exists():
                return []
            return [path.relative_to(self.base).as_posix() for path in self.base.rglob("*.jpg")
                    if path.is_file() and self._is_evidence_key(path.relative_to(self.base).as_posix())
                    and path.relative_to(self.base).as_posix() not in active_keys
                    and datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) < before][:limit]
        keys = await asyncio.to_thread(candidates)
        for key in keys:
            await self.delete(key)
        return len(keys)
