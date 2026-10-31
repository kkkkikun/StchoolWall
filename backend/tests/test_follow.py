"""关注关系测试：关注/取关/幂等/不能关注自己/关注流。"""

import pytest
from httpx import AsyncClient

from app.models.user import User
from app.utils.security import create_access_token
from tests.conftest import TestSession, auth_header


def _token(u: User) -> str:
    return create_access_token({"sub": str(u.id), "role": u.role})


async def _seed_post(user_id, content="帖", status=1):
    from app.models.post import Post
    async with TestSession() as db:
        p = Post(user_id=user_id, post_type="general", content=content, status=status)
        db.add(p); await db.commit(); await db.refresh(p); return p


class TestFollow:
    @pytest.mark.asyncio
    async def test_follow_and_idempotent(self, client: AsyncClient, student_user: User, admin_user: User):
        r = await client.post(f"/api/v1/users/{admin_user.id}/follow", headers=auth_header(_token(student_user)))
        assert r.status_code == 200 and r.json()["data"]["followed"] is True
        # 幂等
        r2 = await client.post(f"/api/v1/users/{admin_user.id}/follow", headers=auth_header(_token(student_user)))
        assert r2.json()["data"]["followed"] is True

    @pytest.mark.asyncio
    async def test_cannot_follow_self(self, client: AsyncClient, student_user: User):
        r = await client.post(f"/api/v1/users/{student_user.id}/follow", headers=auth_header(_token(student_user)))
        assert r.json()["data"]["followed"] is False

    @pytest.mark.asyncio
    async def test_unfollow(self, client: AsyncClient, student_user: User, admin_user: User):
        await client.post(f"/api/v1/users/{admin_user.id}/follow", headers=auth_header(_token(student_user)))
        r = await client.delete(f"/api/v1/users/{admin_user.id}/follow", headers=auth_header(_token(student_user)))
        assert r.json()["data"]["followed"] is False

    @pytest.mark.asyncio
    async def test_guest_cannot_follow(self, client: AsyncClient, guest_user: User, admin_user: User):
        r = await client.post(f"/api/v1/users/{admin_user.id}/follow", headers=auth_header(_token(guest_user)))
        assert r.status_code == 403


class TestFollowingFeed:
    @pytest.mark.asyncio
    async def test_feed_only_followed(self, client: AsyncClient, student_user: User, admin_user: User, guest_user: User):
        """关注流只含已关注用户的帖子"""
        await _seed_post(admin_user.id, content="管理员帖")
        await _seed_post(guest_user.id, content="游客帖")  # 用另一个用户模拟未关注的人
        # student 关注 admin
        await client.post(f"/api/v1/users/{admin_user.id}/follow", headers=auth_header(_token(student_user)))
        r = await client.get("/api/v1/posts/following", headers=auth_header(_token(student_user)))
        assert r.status_code == 200
        items = r.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["content"] == "管理员帖"

    @pytest.mark.asyncio
    async def test_feed_requires_auth(self, client: AsyncClient):
        r = await client.get("/api/v1/posts/following")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_feed_empty_when_no_follow(self, client: AsyncClient, student_user: User, admin_user: User):
        await _seed_post(admin_user.id, content="管理员帖")
        r = await client.get("/api/v1/posts/following", headers=auth_header(_token(student_user)))
        assert r.json()["data"]["items"] == []
