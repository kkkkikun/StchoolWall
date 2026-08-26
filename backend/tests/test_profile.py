"""个人主页测试：公开资料、关注/粉丝列表、主页帖子。"""

import pytest
from httpx import AsyncClient

from app.models.user import User
from app.utils.security import create_access_token
from tests.conftest import TestSession, auth_header


def _token(u: User) -> str:
    return create_access_token({"sub": str(u.id), "role": u.role})


async def _seed_post(user_id, content="主页帖", status=1):
    from app.models.post import Post
    async with TestSession() as db:
        p = Post(user_id=user_id, post_type="general", content=content, status=status)
        db.add(p); await db.commit(); await db.refresh(p); return p


class TestProfile:
    @pytest.mark.asyncio
    async def test_profile_counts(self, client: AsyncClient, admin_user: User, student_user: User):
        """student 关注 admin，admin 发 2 帖 → admin 的资料计数正确"""
        await _seed_post(admin_user.id, content="帖1")
        await _seed_post(admin_user.id, content="帖2")
        await client.post(f"/api/v1/users/{admin_user.id}/follow", headers=auth_header(_token(student_user)))
        r = await client.get(f"/api/v1/users/{admin_user.id}/profile")
        d = r.json()["data"]
        assert d["nickname"] == admin_user.nickname
        assert d["posts_count"] >= 2
        assert d["followers_count"] == 1
        assert d["is_following"] is False  # 游客视角

        # student 视角：is_following=true，is_self=false
        r2 = await client.get(f"/api/v1/users/{admin_user.id}/profile", headers=auth_header(_token(student_user)))
        d2 = r2.json()["data"]
        assert d2["is_following"] is True
        assert d2["is_self"] is False
        assert d2["following_count"] == 0  # admin 没关注任何人

        # admin 看自己：is_self=true
        r3 = await client.get(f"/api/v1/users/{admin_user.id}/profile", headers=auth_header(_token(admin_user)))
        assert r3.json()["data"]["is_self"] is True

    @pytest.mark.asyncio
    async def test_profile_404(self, client: AsyncClient):
        r = await client.get("/api/v1/users/00000000-0000-0000-0000-000000000000/profile")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_profile_no_real_name(self, client: AsyncClient, admin_user: User):
        """资料不暴露 real_name / wechat_id / student_id"""
        r = await client.get(f"/api/v1/users/{admin_user.id}/profile")
        d = r.json()["data"]
        for k in ("real_name", "wechat_id", "student_id", "openid"):
            assert k not in d


class TestFollowingFollowersList:
    @pytest.mark.asyncio
    async def test_lists(self, client: AsyncClient, admin_user: User, student_user: User):
        """student 关注 admin：admin 的 followers 有 student；student 的 following 有 admin"""
        await client.post(f"/api/v1/users/{admin_user.id}/follow", headers=auth_header(_token(student_user)))

        r1 = await client.get(f"/api/v1/users/{student_user.id}/following")
        items = r1.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["id"] == str(admin_user.id)
        assert items[0]["is_following"] is False  # 游客视角

        r2 = await client.get(f"/api/v1/users/{admin_user.id}/followers")
        items2 = r2.json()["data"]["items"]
        assert len(items2) == 1
        assert items2[0]["id"] == str(student_user.id)


class TestUserPosts:
    @pytest.mark.asyncio
    async def test_user_posts_public(self, client: AsyncClient, admin_user: User, student_user: User):
        """主页帖子只含 status=1 非广告，只属于该用户"""
        await _seed_post(admin_user.id, content="admin 可见帖")
        await _seed_post(admin_user.id, content="admin 待审帖", status=0)
        await _seed_post(student_user.id, content="别人的帖")

        r = await client.get(f"/api/v1/users/{admin_user.id}/posts")
        items = r.json()["data"]["items"]
        assert all(i["user"]["nickname"] == admin_user.nickname for i in items)
        assert all("待审" not in i["content"] for i in items)
        assert any(i["content"] == "admin 可见帖" for i in items)
        assert all(i["content"] != "别人的帖" for i in items)
