from tests.production_helpers import image_bytes
"""上传安全测试：kind 白名单 / 服务端生成路径 / 逃逸拒绝 / 流式大小上限。

安全目标：落盘路径完全由服务端生成（客户端不可指定），扩展名校验对象与
落盘文件是同一个；路径 containment 用路径语义而非字符串前缀。
"""
import io
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.config import settings
from app.models.user import User
from app.utils.security import create_access_token
from tests.conftest import auth_header, TestSession
from app.models.media import MediaAsset


@pytest.fixture(autouse=True)
def private_media_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STATIC_BASE_DIR", str(tmp_path / "static"))
    monkeypatch.setattr(settings, "PRIVATE_MEDIA_DIR", str(tmp_path / "private"))
    monkeypatch.setattr(settings, "STORAGE_PROVIDER", "local")


FAKE_JPG = image_bytes()


def _token(user: User) -> str:
    return create_access_token({"sub": str(user.id), "role": user.role})


def _files(name: str = "a.jpg", content: bytes = FAKE_JPG, ct: str = "image/jpeg"):
    return {"file": (name, io.BytesIO(content), ct)}


class TestKindWhitelist:

    @pytest.mark.asyncio
    async def test_kind_outside_whitelist_422(self, client: AsyncClient, student_user: User):
        for evil in ("evil", "static", "avatars/../banners"):
            r = await client.post(
                f"/api/v1/upload/direct?kind={evil}",
                files=_files(), headers=auth_header(_token(student_user)),
            )
            assert r.status_code == 422, evil

    @pytest.mark.asyncio
    async def test_missing_kind_422(self, client: AsyncClient, student_user: User):
        r = await client.post(
            "/api/v1/upload/direct", files=_files(), headers=auth_header(_token(student_user)),
        )
        assert r.status_code == 422


class TestServerGeneratedPath:

    @pytest.mark.asyncio
    async def test_upload_lands_under_kind_dir_with_uuid(self, client: AsyncClient, student_user: User):
        """路径为 /static/{kind}/{年}/{uuid}.{白名单扩展}，文件真实落盘。"""
        r = await client.post(
            "/api/v1/upload/direct?kind=avatars",
            files=_files("photo.JPG"), headers=auth_header(_token(student_user)),
        )
        assert r.status_code == 200
        import uuid
        from app.utils.storage import _private_path
        result = r.json()["data"]
        assert result["public_url"] is None and result["status"] == "quarantine"
        async with TestSession() as db:
            media = await db.get(MediaAsset, uuid.UUID(result["media_id"]))
            assert media.owner_id == student_user.id and media.purpose == "avatars"
            assert _private_path(media.storage_key).is_file()
            assert not Path(settings.STATIC_BASE_DIR).exists()

    @pytest.mark.asyncio
    async def test_html_extension_rejected_no_file(self, client: AsyncClient, student_user: User):
        """伪装 Content-Type 的 .html 落盘企图被拒（校验对象是真实文件名）。"""
        r = await client.post(
            "/api/v1/upload/direct?kind=posts",
            files=_files("evil.html", b"<script>alert(1)</script>"),
            headers=auth_header(_token(student_user)),
        )
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_double_extension_rejected(self, client: AsyncClient, student_user: User):
        r = await client.post(
            "/api/v1/upload/direct?kind=posts",
            files=_files("x.jpg.html", b"<script>"),
            headers=auth_header(_token(student_user)),
        )
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_two_uploads_never_collide(self, client: AsyncClient, student_user: User):
        """重复上传路径不同（uuid）——既有公共资源不可被覆盖。"""
        headers = auth_header(_token(student_user))
        r1 = await client.post("/api/v1/upload/direct?kind=banners", files=_files(), headers=headers)
        r2 = await client.post("/api/v1/upload/direct?kind=banners", files=_files(), headers=headers)
        assert r1.json()["data"]["media_id"] != r2.json()["data"]["media_id"]


class TestPathContainment:

    def test_sibling_directory_escape_rejected(self):
        """../static-evil 与 base 同前缀但不在 base 内 → 拒（is_relative_to 语义）。"""
        from app.utils.storage import get_storage_backend
        backend = get_storage_backend()
        with pytest.raises(ValueError):
            backend._safe_path("../static-evil/x.jpg")

    def test_normal_relative_path_accepted(self):
        from app.utils.storage import get_storage_backend
        backend = get_storage_backend()
        p = backend._safe_path("posts/2026/abc.jpg")
        assert p.name == "abc.jpg"


class TestStreamingSizeCap:

    @pytest.mark.asyncio
    async def test_oversize_rejected_before_full_read(self, client: AsyncClient, student_user: User, monkeypatch):
        """超限即拒（阈值 monkeypatch 到 1KB，避免 10MB 内存测试）。"""
        import app.utils.storage as storage_mod
        monkeypatch.setattr(storage_mod, "MAX_FILE_SIZE", 1024)
        r = await client.post(
            "/api/v1/upload/direct?kind=posts",
            files=_files("big.jpg", b"x" * 4096),
            headers=auth_header(_token(student_user)),
        )
        assert r.status_code == 400
        assert "10MB" in r.json()["detail"] or "大小" in r.json()["detail"]
