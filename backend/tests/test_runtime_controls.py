import pytest
from sqlalchemy import select

from app.models.admin_log import AdminLog
from app.models.post import Post
from tests.conftest import TestSession, auth_header

pytestmark = pytest.mark.asyncio


async def _set_controls(client, console_headers, **changes):
    response = await client.put("/api/v1/admin/runtime-controls", headers=console_headers, json=changes)
    assert response.status_code == 200
    return response.json()["data"]


async def _public_post(client, user_id) -> int:
    async with TestSession() as db:
        post = Post(user_id=user_id, post_type="general", content="互动宿主帖", status=1)
        db.add(post)
        await db.commit()
        await db.refresh(post)
        return post.id


async def test_controls_default_partial_update_and_audit(client, console_headers, console_admin):
    response = await client.get("/api/v1/runtime-controls")
    assert response.status_code == 200
    assert response.json()["data"] == {
        "publishing_enabled": True,
        "moderation_enabled": True,
        "sensitive_words_enabled": True,
        "registration_enabled": True,
        "guest_posting_enabled": False,
        "guest_interaction_enabled": False,
    }

    data = await _set_controls(client, console_headers, guest_posting_enabled=True)
    assert data["guest_posting_enabled"] is True
    assert data["moderation_enabled"] is True
    response = await client.get("/api/v1/admin/runtime-controls", headers=console_headers)
    assert response.json()["data"]["guest_posting_enabled"] is True

    async with TestSession() as db:
        log = (await db.execute(select(AdminLog).where(AdminLog.action == "runtime.controls"))).scalar_one()
        assert log.admin_id == str(console_admin.id)
        assert log.detail == {"guest_posting_enabled": True}


async def test_controls_require_admin_and_nonempty_change(client, student_token, console_headers):
    response = await client.get("/api/v1/admin/runtime-controls", headers=auth_header(student_token))
    assert response.status_code == 403
    response = await client.put("/api/v1/admin/runtime-controls", headers=console_headers, json={})
    assert response.status_code == 400


async def test_registration_switch_preserves_existing_login(client, console_headers, student_user):
    await _set_controls(client, console_headers, registration_enabled=False)
    response = await client.post("/api/v1/auth/register", json={
        "username": "closed_beta_user", "password": "VerySecure123",
    })
    assert response.status_code == 403
    assert response.json()["detail"] == "内测注册暂未开放，请使用已有账号登录"


async def test_guest_posting_and_interaction_switches(
    client, console_headers, guest_user, guest_token, student_user,
):
    headers = auth_header(guest_token)
    post_id = await _public_post(client, student_user.id)
    response = await client.post("/api/v1/posts", headers=headers, json={
        "post_type": "general", "content": "游客内测帖",
    })
    assert response.status_code == 403
    response = await client.post(f"/api/v1/posts/{post_id}/like", headers=headers)
    assert response.status_code == 403

    await _set_controls(
        client, console_headers, guest_posting_enabled=True, guest_interaction_enabled=True,
    )
    response = await client.post("/api/v1/posts", headers=headers, json={
        "post_type": "general", "content": "游客内测帖",
    })
    assert response.status_code == 200
    response = await client.post(f"/api/v1/posts/{post_id}/like", headers=headers)
    assert response.status_code == 200
    response = await client.post(f"/api/v1/posts/{post_id}/comments", headers=headers, json={
        "content": "游客内测评论",
    })
    assert response.status_code == 200
    response = await client.post("/api/v1/parties", headers=headers, json={
        "type": "group", "category": "自习", "title": "游客自习局",
        "content": "图书馆一起学习", "total": 3,
    })
    assert response.status_code == 200
    response = await client.get("/api/v1/upload/config", headers=headers, params={
        "filename": "guest.jpg", "content_type": "image/jpeg",
    })
    assert response.status_code == 200

    await _set_controls(
        client, console_headers, guest_posting_enabled=False, guest_interaction_enabled=False,
    )
    response = await client.post(f"/api/v1/posts/{post_id}/like", headers=headers)
    assert response.status_code == 403


async def test_moderation_switch_publishes_new_content_immediately(
    client, console_headers, student_user, student_token,
):
    post_id = await _public_post(client, student_user.id)
    await _set_controls(client, console_headers, moderation_enabled=False)
    headers = auth_header(student_token)

    response = await client.post("/api/v1/posts", headers=headers, json={
        "post_type": "general", "content": "免审核内测帖",
    })
    assert response.status_code == 200
    assert response.json()["data"]["status"] == 1
    new_post_id = response.json()["data"]["post_id"]
    response = await client.get(f"/api/v1/posts/{new_post_id}")
    assert response.status_code == 200

    response = await client.post(f"/api/v1/posts/{post_id}/comments", headers=headers, json={
        "content": "免审核内测评论",
    })
    assert response.status_code == 200
    assert response.json()["data"]["status"] == 1

    response = await client.post("/api/v1/parties", headers=headers, json={
        "type": "group", "category": "自习", "title": "免审核内测局",
        "content": "今晚图书馆", "total": 4,
    })
    assert response.status_code == 200
    assert response.json()["data"]["status"] == 1


async def test_sensitive_word_switch_and_hard_rule_with_moderation_off(
    client, console_headers, student_user, student_token,
):
    response = await client.post("/api/v1/admin/sensitive-words", headers=console_headers, json={
        "word": "内测硬违规", "level": "hard",
    })
    assert response.status_code == 200
    headers = auth_header(student_token)
    post_id = await _public_post(client, student_user.id)

    response = await client.post(f"/api/v1/posts/{post_id}/comments", headers=headers, json={
        "content": "包含内测硬违规",
    })
    assert response.status_code == 400

    await _set_controls(client, console_headers, sensitive_words_enabled=False)
    response = await client.post(f"/api/v1/posts/{post_id}/comments", headers=headers, json={
        "content": "包含内测硬违规",
    })
    assert response.status_code == 200
    assert response.json()["data"]["status"] == 0

    await _set_controls(
        client, console_headers, sensitive_words_enabled=True, moderation_enabled=False,
    )
    response = await client.post("/api/v1/posts", headers=headers, json={
        "post_type": "general", "content": "包含内测硬违规",
    })
    assert response.status_code == 400
