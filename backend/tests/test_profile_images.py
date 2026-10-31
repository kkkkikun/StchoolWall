"""Profile drafts expose media and text only after a current moderation decision."""
import uuid

import pytest

from app.config import settings
from app.models.job import Job
from app.models.user import User
from app.utils.security import create_access_token
from tests.conftest import TestSession, auth_header
from tests.production_helpers import approve_profile, image_bytes


def _token(user):
    return create_access_token({"sub": str(user.id), "role": user.role})


@pytest.fixture(autouse=True)
def _private_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_PROVIDER", "local")
    monkeypatch.setattr(settings, "PRIVATE_MEDIA_DIR", str(tmp_path / "private"))


async def _upload(client, token, kind):
    response = await client.post("/api/v1/upload/direct", params={"kind": kind},
        files={"file": ("profile.jpg", image_bytes(), "image/jpeg")}, headers=auth_header(token))
    assert response.status_code == 200, response.text
    return response.json()["data"]["media_id"]


class TestAvatarBanner:
    async def test_update_and_readback(self, client, student_user):
        token = _token(student_user)
        avatar_id = await _upload(client, token, "avatars")
        banner_id = await _upload(client, token, "banners")
        response = await client.put("/api/v1/user/profile", json={
            "avatar_media_id": avatar_id, "banner_media_id": banner_id,
        }, headers=auth_header(token))
        assert response.status_code == 200, response.text
        assert response.json()["data"]["status"] == "pending"
        before = (await client.get("/api/v1/user/profile", headers=auth_header(token))).json()["data"]
        assert before["avatar_url"] is None and before["banner_url"] is None
        await approve_profile(response.json()["data"]["job_id"])
        after = (await client.get("/api/v1/user/profile", headers=auth_header(token))).json()["data"]
        assert after["avatar_url"] == f"/api/v1/upload/media/{avatar_id}/content"
        assert after["banner_url"] == f"/api/v1/upload/media/{banner_id}/content"
        assert (await client.get(after["avatar_url"])).status_code == 200

    async def test_partial_update_keeps_other_fields(self, client, student_user):
        token = _token(student_user)
        banner_id = await _upload(client, token, "banners")
        response = await client.put("/api/v1/user/profile", json={"banner_media_id": banner_id}, headers=auth_header(token))
        await approve_profile(response.json()["data"]["job_id"])
        avatar_id = await _upload(client, token, "avatars")
        response = await client.put("/api/v1/user/profile", json={"avatar_media_id": avatar_id}, headers=auth_header(token))
        await approve_profile(response.json()["data"]["job_id"])
        after = (await client.get("/api/v1/user/profile", headers=auth_header(token))).json()["data"]
        assert after["avatar_url"] == f"/api/v1/upload/media/{avatar_id}/content"
        assert after["banner_url"] == f"/api/v1/upload/media/{banner_id}/content"

    async def test_require_login(self, client):
        response = await client.put("/api/v1/user/profile", json={"avatar_url": "/a.png"})
        assert response.status_code == 401

    async def test_profile_rejects_wrong_purpose_and_other_owner(self, client, student_user, admin_user):
        token = _token(student_user)
        wrong_purpose = await _upload(client, token, "posts")
        foreign_asset = await _upload(client, _token(admin_user), "avatars")
        for media_id in (wrong_purpose, foreign_asset):
            response = await client.put("/api/v1/user/profile", json={"avatar_media_id": media_id}, headers=auth_header(token))
            assert response.status_code == 400


class TestBio:
    async def test_bio_roundtrip(self, client, student_user):
        token = _token(student_user)
        response = await client.put("/api/v1/user/profile", json={"bio": "热爱生活，热爱分享～"}, headers=auth_header(token))
        assert response.status_code == 200
        before = await client.get("/api/v1/user/profile", headers=auth_header(token))
        assert before.json()["data"]["bio"] is None
        await approve_profile(response.json()["data"]["job_id"])
        after = await client.get("/api/v1/user/profile", headers=auth_header(token))
        assert after.json()["data"]["bio"] == "热爱生活，热爱分享～"

    async def test_older_draft_cannot_overwrite_newer_draft(self, client, student_user):
        token = _token(student_user)
        old = await client.put("/api/v1/user/profile", json={"bio": "第一份资料"}, headers=auth_header(token))
        new = await client.put("/api/v1/user/profile", json={"bio": "新的资料"}, headers=auth_header(token))
        await approve_profile(old.json()["data"]["job_id"])
        before = (await client.get("/api/v1/user/profile", headers=auth_header(token))).json()["data"]
        assert before["bio"] is None
        await approve_profile(new.json()["data"]["job_id"])
        await approve_profile(old.json()["data"]["job_id"])
        after = (await client.get("/api/v1/user/profile", headers=auth_header(token))).json()["data"]
        assert after["bio"] == "新的资料"

    async def test_rejected_draft_keeps_current_public_fields(self, client, student_user, monkeypatch):
        import app.services.moderation as service
        from app.utils.moderation import ModerationResult
        token = _token(student_user)
        response = await client.put("/api/v1/user/profile", json={"bio": "测试待拒绝资料"}, headers=auth_header(token))
        async with TestSession() as db:
            payload = (await db.get(Job, uuid.UUID(response.json()["data"]["job_id"]))).payload
        async def rejected(*args):
            return ModerationResult("reject")
        monkeypatch.setattr(service, "async_session", TestSession)
        monkeypatch.setattr(service, "check_text", rejected)
        with pytest.raises(service.ContentRejected):
            await service.check_profile_moderation(payload)
        after = (await client.get("/api/v1/user/profile", headers=auth_header(token))).json()["data"]
        assert after["bio"] is None

    async def test_bio_too_long_rejected(self, client, student_user):
        response = await client.put("/api/v1/user/profile", json={"bio": "x" * 201}, headers=auth_header(_token(student_user)))
        assert response.status_code == 422

async def test_public_contact_field_is_included_in_profile_moderation(client, student_user, monkeypatch):
    import app.services.moderation as service
    from app.utils.moderation import ModerationResult
    token = _token(student_user)
    response = await client.put("/api/v1/user/profile", json={"wechat_id": "public_contact_123"}, headers=auth_header(token))
    async with TestSession() as db:
        payload = (await db.get(Job, uuid.UUID(response.json()["data"]["job_id"]))).payload
    seen = []
    async def checked(content, *args):
        seen.append(content)
        return ModerationResult("pass")
    monkeypatch.setattr(service, "async_session", TestSession)
    monkeypatch.setattr(service, "check_text", checked)
    await service.check_profile_moderation(payload)
    assert any("public_contact_123" in content for content in seen)
    after = (await client.get("/api/v1/user/profile", headers=auth_header(token))).json()["data"]
    assert after["wechat_id"] == "public_contact_123"
