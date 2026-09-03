"""热门用户榜测试：按帖子获赞总数排序，公开访问，广告不计热。"""

import pytest
from httpx import AsyncClient

from app.models.post import Post
from app.models.user import User
from tests.conftest import TestSession


async def _seed_post(user_id, likes, post_type="general", status=1):
    async with TestSession() as db:
        db.add(Post(user_id=user_id, post_type=post_type, content="x", status=status, like_count=likes))
        await db.commit()


class TestHotRanking:

    @pytest.mark.asyncio
    async def test_ordering_and_heat(self, client: AsyncClient, student_user: User, admin_user: User):
        await _seed_post(student_user.id, 100)
        await _seed_post(student_user.id, 28)          # 同一用户累加
        await _seed_post(admin_user.id, 50)
        await _seed_post(admin_user.id, 999, post_type="advertisement")  # 广告不计
        await _seed_post(admin_user.id, 7, status=-1)  # 封禁帖不计

        r = await client.get("/api/v1/user/hot-ranking")
        assert r.status_code == 200
        items = r.json()["data"]["items"]
        top = items[0]
        assert top["id"] == str(student_user.id)
        assert top["heat"] == 128
        second = next(i for i in items if i["id"] == str(admin_user.id))
        assert second["heat"] == 50  # 广告 999 与封禁 7 都被排除

    @pytest.mark.asyncio
    async def test_public_and_limit(self, client: AsyncClient, student_user: User):
        await _seed_post(student_user.id, 5)
        r = await client.get("/api/v1/user/hot-ranking?limit=1")
        items = r.json()["data"]["items"]
        assert r.status_code == 200
        assert len(items) <= 1

    @pytest.mark.asyncio
    async def test_empty_ok(self, client: AsyncClient):
        r = await client.get("/api/v1/user/hot-ranking")
        assert r.status_code == 200
        assert r.json()["data"]["items"] == []
