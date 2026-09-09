"""列表接口头像透出测试：信息流与热门用户榜需返回作者头像。"""
import pytest
from httpx import AsyncClient

from app.models.user import User
from app.utils.security import create_access_token
from tests.conftest import TestSession, auth_header


def _token(user: User) -> str:
    return create_access_token({"sub": str(user.id), "role": user.role})


async def _set_avatar(user: User, url: str):
    async with TestSession() as db:
        u = await db.get(User, user.id)
        u.avatar_url = url
        await db.commit()


class TestFeedAvatar:

    @pytest.mark.asyncio
    async def test_feed_items_include_avatar(self, client: AsyncClient, admin_user: User):
        """信息流列表项携带作者头像 URL（前端渲染真实头像）。admin 发帖即过审可进 feed。"""
        await _set_avatar(admin_user, "/static/avatars/2026/abc.jpg")
        await client.post(
            "/api/v1/posts",
            json={"post_type": "general", "content": "头像透出测试帖"},
            headers=auth_header(_token(admin_user)),
        )
        r = await client.get("/api/v1/posts")
        items = r.json()["data"]["items"]
        mine = [i for i in items if i["user"]["nickname"] == admin_user.nickname]
        assert mine, "帖子未进 feed"
        assert mine[0]["user"]["avatar_url"] == "/static/avatars/2026/abc.jpg"

    @pytest.mark.asyncio
    async def test_my_posts_include_avatar(self, client: AsyncClient, student_user: User):
        """我的帖子列表同样携带头像。"""
        await _set_avatar(student_user, "/static/avatars/2026/xyz.png")
        await client.post(
            "/api/v1/posts",
            json={"post_type": "general", "content": "我的帖子头像"},
            headers=auth_header(_token(student_user)),
        )
        r = await client.get("/api/v1/posts/my", headers=auth_header(_token(student_user)))
        items = r.json()["data"]["items"]
        assert any(i["user"].get("avatar_url") == "/static/avatars/2026/xyz.png" for i in items)


class TestHotRankingAvatar:

    @pytest.mark.asyncio
    async def test_hot_ranking_includes_avatar(self, client: AsyncClient, admin_user: User):
        """热门用户榜携带头像 URL（admin 帖即过审进热度口径）。"""
        await _set_avatar(admin_user, "/static/avatars/2026/rank.jpg")
        await client.post(
            "/api/v1/posts",
            json={"post_type": "general", "content": "热榜头像测试帖"},
            headers=auth_header(_token(admin_user)),
        )
        r = await client.get("/api/v1/user/hot-ranking")
        items = r.json()["data"]["items"]
        me = [i for i in items if i["nickname"] == admin_user.nickname]
        assert me
        assert me[0]["avatar_url"] == "/static/avatars/2026/rank.jpg"
