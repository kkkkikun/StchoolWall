"""批5：/static 挂载 + 管理端图片上传测试。"""
import io

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header



def _jpg(name="banner.jpg"):
    return {"file": (name, io.BytesIO(b"\xff\xd8\xff\xe0fakejpg"), "image/jpeg")}


class TestAdminImageUpload:
    async def test_upload_success(self, client: AsyncClient, console_headers: dict):
        r = await client.post("/api/v1/admin/upload/image", files=_jpg(), headers=console_headers)
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["public_url"].startswith("/static/banners/")
        assert data["public_url"].endswith(".jpg")

    async def test_legacy_admin_token_accepted(self, client: AsyncClient, admin_token: str):
        """双 token：legacy users.admin 也能上传。"""
        r = await client.post("/api/v1/admin/upload/image", files=_jpg(),
                              headers=auth_header(admin_token))
        assert r.status_code == 200

    async def test_student_token_403(self, client: AsyncClient, student_token: str):
        r = await client.post("/api/v1/admin/upload/image", files=_jpg(),
                              headers=auth_header(student_token))
        assert r.status_code == 403

    async def test_reject_non_image_400(self, client: AsyncClient, console_headers: dict):
        files = {"file": ("evil.exe", io.BytesIO(b"MZ"), "application/octet-stream")}
        r = await client.post("/api/v1/admin/upload/image", files=files, headers=console_headers)
        assert r.status_code == 400

    async def test_writes_audit(self, client: AsyncClient, console_headers: dict):
        from sqlalchemy import select
        from app.models.admin_log import AdminLog
        from tests.conftest import TestSession
        await client.post("/api/v1/admin/upload/image", files=_jpg(), headers=console_headers)
        async with TestSession() as db:
            log = (await db.execute(select(AdminLog).where(AdminLog.action == "image.upload"))).scalar_one()
            assert log.detail["filename"] == "banner.jpg"


class TestStaticFiles:
    async def test_static_serves_uploaded_file(self, client: AsyncClient, console_headers: dict):
        """上传后 /static/{path} 可直接访问。"""
        r = await client.post("/api/v1/admin/upload/image", files=_jpg(), headers=console_headers)
        url = r.json()["data"]["public_url"]
        r2 = await client.get(url)
        assert r2.status_code == 200
        assert r2.content == b"\xff\xd8\xff\xe0fakejpg"

    async def test_static_unknown_404(self, client: AsyncClient):
        r = await client.get("/static/banners/no_such_file.jpg")
        assert r.status_code == 404


class TestSafePath:
    async def test_client_path_is_ignored(self, client: AsyncClient, student_token: str):
        """安全收紧后客户端只能传 kind：恶意 path 参数不再被接受（缺 kind → 422），
        携带 kind 时文件也只落在服务端生成的 kind 目录下。"""
        files = _jpg()
        r = await client.post(
            "/api/v1/upload/direct?path=../etc/pwned.jpg",
            files=files, headers=auth_header(student_token),
        )
        assert r.status_code == 422  # 无 kind 参数
        r2 = await client.post(
            "/api/v1/upload/direct?kind=banners&path=../etc/pwned.jpg",
            files=files, headers=auth_header(student_token),
        )
        assert r2.status_code == 200
        assert r2.json()["data"]["public_url"].startswith("/static/banners/")

    def test_safe_path_unit(self):
        from app.utils.storage import LocalStorage
        ls = LocalStorage()
        # 正常路径 OK
        ok = ls._safe_path("banners/2026/abc.jpg")
        assert str(ok).startswith(str(ls.base_dir.resolve()))
        # 穿越 rejected
        with pytest.raises(ValueError):
            ls._safe_path("../outside.jpg")
        with pytest.raises(ValueError):
            ls._safe_path("posts/../../etc/passwd")
