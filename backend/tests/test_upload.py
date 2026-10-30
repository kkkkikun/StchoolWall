from tests.production_helpers import image_bytes
"""Upload 模块测试：上传配置、本地直传、权限控制、文件校验"""

import io
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch, MagicMock

from app.models.user import User
from app.utils.security import create_access_token
from tests.conftest import TestSession, auth_header


@pytest.fixture(autouse=True)
def private_media_dirs(tmp_path, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "STATIC_BASE_DIR", str(tmp_path / "static"))
    monkeypatch.setattr(settings, "PRIVATE_MEDIA_DIR", str(tmp_path / "private"))
    monkeypatch.setattr(settings, "STORAGE_PROVIDER", "local")



# ============================================================
# GET /api/v1/upload/config — 获取上传配置
# ============================================================


class TestGetUploadConfig:

    @pytest.mark.asyncio
    async def test_local_config(self, client: AsyncClient, student_user: User):
        """local 模式返回 POST 策略和 direct 接口地址"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.get(
            "/api/v1/upload/config",
            params={"filename": "photo.jpg", "content_type": "image/jpeg"},
            headers=auth_header(token),
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["provider"] == "proxy"
        assert data["method"] == "POST"
        assert "/api/v1/upload/direct" in data["upload_url"]
        assert data["public_url"] is None
        assert data["form_data"] is not None
        assert "path" not in data["form_data"]

    @pytest.mark.asyncio
    async def test_object_store_config_still_uses_verifying_proxy(self, client, student_user, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "STORAGE_PROVIDER", "r2")
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        response = await client.get("/api/v1/upload/config",
                                    params={"filename": "photo.jpg", "content_type": "image/jpeg"},
                                    headers=auth_header(token))
        assert response.status_code == 200
        assert response.json()["data"]["provider"] == "proxy"
        assert response.json()["data"]["public_url"] is None

    @pytest.mark.asyncio
    async def test_admin_can_get_config(self, client: AsyncClient, admin_user: User):
        """admin 也能获取上传配置"""
        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        r = await client.get(
            "/api/v1/upload/config",
            params={"filename": "img.png", "content_type": "image/png"},
            headers=auth_header(token),
        )
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_guest_cannot_get_config(self, client: AsyncClient, guest_user: User):
        """guest 无权获取上传配置"""
        token = create_access_token({"sub": str(guest_user.id), "role": "guest"})
        r = await client.get(
            "/api/v1/upload/config",
            params={"filename": "img.jpg", "content_type": "image/jpeg"},
            headers=auth_header(token),
        )
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_no_token_rejected(self, client: AsyncClient):
        """无 Token 被拒绝"""
        r = await client.get(
            "/api/v1/upload/config",
            params={"filename": "img.jpg", "content_type": "image/jpeg"},
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_file_type_rejected(self, client: AsyncClient, student_user: User):
        """非图片文件类型被拒绝"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.get(
            "/api/v1/upload/config",
            params={"filename": "malware.exe", "content_type": "application/octet-stream"},
            headers=auth_header(token),
        )
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_invalid_content_type_rejected(self, client: AsyncClient, student_user: User):
        """content_type 非 image 被拒绝"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.get(
            "/api/v1/upload/config",
            params={"filename": "photo.jpg", "content_type": "video/mp4"},
            headers=auth_header(token),
        )
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_missing_filename_rejected(self, client: AsyncClient, student_user: User):
        """缺少 filename 参数返回 422"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.get(
            "/api/v1/upload/config",
            params={"content_type": "image/jpeg"},
            headers=auth_header(token),
        )
        assert r.status_code == 422


# ============================================================
# POST /api/v1/upload/direct — 本地直接上传
# ============================================================


class TestDirectUpload:

    @pytest.mark.asyncio
    async def test_upload_success(self, client: AsyncClient, student_user: User):
        """上传图片成功，返回 public_url"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        files = {"file": ("test.jpg", io.BytesIO(image_bytes()), "image/jpeg")}
        r = await client.post(
            "/api/v1/upload/direct?kind=posts",
            files=files,
            headers=auth_header(token),
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["public_url"] is None
        assert data["media_id"]
        assert data["status"] == "quarantine"

    @pytest.mark.asyncio
    async def test_upload_png(self, client: AsyncClient, student_user: User):
        """上传 PNG 格式"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        files = {"file": ("img.png", io.BytesIO(image_bytes("PNG")), "image/png")}
        r = await client.post(
            "/api/v1/upload/direct?kind=posts",
            files=files,
            headers=auth_header(token),
        )
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_upload_rejects_non_image(self, client: AsyncClient, student_user: User):
        """上传非图片文件被拒绝"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        files = {"file": ("doc.pdf", io.BytesIO(b"pdf content"), "application/pdf")}
        r = await client.post(
            "/api/v1/upload/direct?kind=posts",
            files=files,
            headers=auth_header(token),
        )
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_upload_guest_forbidden(self, client: AsyncClient, guest_user: User):
        """guest 不能上传"""
        token = create_access_token({"sub": str(guest_user.id), "role": "guest"})
        files = {"file": ("test.jpg", io.BytesIO(b"data"), "image/jpeg")}
        r = await client.post(
            "/api/v1/upload/direct?kind=posts",
            files=files,
            headers=auth_header(token),
        )
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_upload_no_token_rejected(self, client: AsyncClient):
        """无 Token 上传被拒绝"""
        files = {"file": ("test.jpg", io.BytesIO(b"data"), "image/jpeg")}
        r = await client.post(
            "/api/v1/upload/direct?kind=posts",
            files=files,
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_upload_missing_path_rejected(self, client: AsyncClient, student_user: User):
        """缺少 kind 参数返回 422"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        files = {"file": ("test.jpg", io.BytesIO(b"data"), "image/jpeg")}
        r = await client.post(
            "/api/v1/upload/direct",
            files=files,
            headers=auth_header(token),
        )
        assert r.status_code == 422
