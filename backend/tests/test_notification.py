from tests.production_helpers import approve_comments
"""消息通知模块测试：触发（评论/赞）、不通知自己、未读汇总、列表、已读。"""

import pytest
from httpx import AsyncClient

from app.models.user import User
from app.utils.security import create_access_token
from tests.conftest import TestSession, auth_header


async def _seed_post(user_id, content="作者帖", status=1):
    from app.models.post import Post
    async with TestSession() as db:
        p = Post(user_id=user_id, post_type="general", content=content, status=status)
        db.add(p)
        await db.commit()
        await db.refresh(p)
        return p


def _token(u: User) -> str:
    return create_access_token({"sub": str(u.id), "role": u.role})


class TestNotificationTrigger:
    @pytest.mark.asyncio
    async def test_comment_notifies_author(self, client: AsyncClient, admin_user: User, student_user: User):
        """评论别人的帖子 → 作者收到 comment 通知"""
        post = await _seed_post(admin_user.id)
        await client.post(f"/api/v1/posts/{post.id}/comments", json={"content": "好帖"},
                          headers=auth_header(_token(student_user)))
        await approve_comments()
        r = await client.get("/api/v1/notifications", headers=auth_header(_token(admin_user)))
        items = r.json()["data"]["items"]
        assert any(n["type"] == "comment" for n in items)

    @pytest.mark.asyncio
    async def test_like_notifies_author(self, client: AsyncClient, admin_user: User, student_user: User):
        post = await _seed_post(admin_user.id)
        await client.post(f"/api/v1/posts/{post.id}/like", headers=auth_header(_token(student_user)))
        r = await client.get("/api/v1/notifications", headers=auth_header(_token(admin_user)))
        items = r.json()["data"]["items"]
        assert any(n["type"] == "like" for n in items)

    @pytest.mark.asyncio
    async def test_no_self_notification(self, client: AsyncClient, admin_user: User):
        """赞/评论自己的帖子 → 不通知自己"""
        post = await _seed_post(admin_user.id)
        await client.post(f"/api/v1/posts/{post.id}/like", headers=auth_header(_token(admin_user)))
        await client.post(f"/api/v1/posts/{post.id}/comments", json={"content": "自评"},
                          headers=auth_header(_token(admin_user)))
        await approve_comments()
        r = await client.get("/api/v1/notifications", headers=auth_header(_token(admin_user)))
        assert r.json()["data"]["items"] == []

    @pytest.mark.asyncio
    async def test_unlike_does_not_remove_notification(self, client: AsyncClient, admin_user: User, student_user: User):
        """取消赞不删除已产生的通知（通知是历史记录）"""
        post = await _seed_post(admin_user.id)
        await client.post(f"/api/v1/posts/{post.id}/like", headers=auth_header(_token(student_user)))
        await client.delete(f"/api/v1/posts/{post.id}/like", headers=auth_header(_token(student_user)))
        r = await client.get("/api/v1/notifications", headers=auth_header(_token(admin_user)))
        assert any(n["type"] == "like" for n in r.json()["data"]["items"])


class TestUnreadSummary:
    @pytest.mark.asyncio
    async def test_summary_counts(self, client: AsyncClient, admin_user: User, student_user: User):
        post = await _seed_post(admin_user.id)
        await client.post(f"/api/v1/posts/{post.id}/like", headers=auth_header(_token(student_user)))
        await client.post(f"/api/v1/posts/{post.id}/comments", json={"content": "hi"},
                          headers=auth_header(_token(student_user)))
        await approve_comments()
        r = await client.get("/api/v1/notifications/unread-summary", headers=auth_header(_token(admin_user)))
        d = r.json()["data"]
        assert d["comment"] == 1
        assert d["like"] == 1
        assert d["group"] == 0
        assert d["im"] == 0

    @pytest.mark.asyncio
    async def test_summary_requires_auth(self, client: AsyncClient):
        r = await client.get("/api/v1/notifications/unread-summary")
        assert r.status_code == 401


class TestReadAndList:
    @pytest.mark.asyncio
    async def test_mark_all_read(self, client: AsyncClient, admin_user: User, student_user: User):
        post = await _seed_post(admin_user.id)
        await client.post(f"/api/v1/posts/{post.id}/like", headers=auth_header(_token(student_user)))
        await client.post("/api/v1/notifications/read-all", headers=auth_header(_token(admin_user)))
        r = await client.get("/api/v1/notifications/unread-summary", headers=auth_header(_token(admin_user)))
        d = r.json()["data"]
        assert d["comment"] + d["like"] + d["group"] + d["im"] == 0

    @pytest.mark.asyncio
    async def test_mark_one_read(self, client: AsyncClient, admin_user: User, student_user: User):
        post = await _seed_post(admin_user.id)
        await client.post(f"/api/v1/posts/{post.id}/like", headers=auth_header(_token(student_user)))
        nid = (await client.get("/api/v1/notifications", headers=auth_header(_token(admin_user)))).json()["data"]["items"][0]["id"]
        r = await client.post(f"/api/v1/notifications/{nid}/read", headers=auth_header(_token(admin_user)))
        assert r.status_code == 200
        # 该条 is_read=true
        items = (await client.get("/api/v1/notifications", headers=auth_header(_token(admin_user)))).json()["data"]["items"]
        assert items[0]["is_read"] is True

    @pytest.mark.asyncio
    async def test_get_one_detail_and_owner_only(self, client: AsyncClient, admin_user: User, student_user: User):
        post = await _seed_post(admin_user.id)
        await client.post(f"/api/v1/posts/{post.id}/like", headers=auth_header(_token(student_user)))
        nid = (await client.get("/api/v1/notifications", headers=auth_header(_token(admin_user)))).json()["data"]["items"][0]["id"]

        r = await client.get(f"/api/v1/notifications/{nid}", headers=auth_header(_token(admin_user)))
        assert r.status_code == 200
        assert r.json()["data"]["type"] == "like"

        # 非接收者不可读
        r = await client.get(f"/api/v1/notifications/{nid}", headers=auth_header(_token(student_user)))
        assert r.status_code == 404

        r = await client.get("/api/v1/notifications/999999", headers=auth_header(_token(admin_user)))
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_list_uses_stable_id_order(self, client: AsyncClient, admin_user: User, student_user: User):
        """消息按稳定的 id 倒序排列，未读数另行汇总。"""
        post = await _seed_post(admin_user.id)
        await client.post(f"/api/v1/posts/{post.id}/like", headers=auth_header(_token(student_user)))
        await client.post(f"/api/v1/posts/{post.id}/comments", json={"content": "x"},
                          headers=auth_header(_token(student_user)))
        await approve_comments()
        items = (await client.get("/api/v1/notifications", headers=auth_header(_token(admin_user)))).json()["data"]["items"]
        assert len(items) == 2
        assert all(n["is_read"] is False for n in items)
        assert items[0]["id"] > items[1]["id"]
