"""发现模块测试：十大热帖 + 搜索。"""

import pytest
from httpx import AsyncClient

from app.models.user import User
from app.utils.security import create_access_token
from tests.conftest import TestSession, auth_header


async def _seed(user_id, content="测试帖", post_type="general", status=1,
                like_count=0, comment_count=0, view_count=0):
    from app.models.post import Post
    async with TestSession() as db:
        p = Post(user_id=user_id, post_type=post_type, content=content, status=status,
                 like_count=like_count, comment_count=comment_count, view_count=view_count)
        db.add(p)
        await db.commit()
        await db.refresh(p)
        return p


class TestHotPosts:
    @pytest.mark.asyncio
    async def test_hot_ordering_by_score(self, client: AsyncClient, admin_user: User):
        """按 like*3 + comment*2 + view 加权倒序"""
        await _seed(admin_user.id, content="低分帖", like_count=0)
        await _seed(admin_user.id, content="高分帖", like_count=5, comment_count=2, view_count=10)
        await _seed(admin_user.id, content="中分帖", like_count=1, comment_count=1)
        r = await client.get("/api/v1/posts/hot")
        assert r.status_code == 200
        items = r.json()["data"]["items"]
        assert items[0]["content"] == "高分帖"
        assert items[1]["content"] == "中分帖"

    @pytest.mark.asyncio
    async def test_hot_excludes_ads(self, client: AsyncClient, admin_user: User):
        """广告不计入热帖"""
        await _seed(admin_user.id, content="广告帖", post_type="advertisement", like_count=100)
        await _seed(admin_user.id, content="正常帖", like_count=1)
        r = await client.get("/api/v1/posts/hot")
        items = r.json()["data"]["items"]
        assert all(i["post_type"] != "advertisement" for i in items)
        assert any(i["content"] == "正常帖" for i in items)

    @pytest.mark.asyncio
    async def test_hot_limit(self, client: AsyncClient, admin_user: User):
        for i in range(15):
            await _seed(admin_user.id, content=f"帖{i}", like_count=i)
        r = await client.get("/api/v1/posts/hot?limit=10")
        assert len(r.json()["data"]["items"]) <= 10

    @pytest.mark.asyncio
    async def test_hot_public(self, client: AsyncClient, admin_user: User):
        """无需登录"""
        await _seed(admin_user.id, like_count=1)
        r = await client.get("/api/v1/posts/hot")
        assert r.status_code == 200


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_match(self, client: AsyncClient, admin_user: User):
        await _seed(admin_user.id, content="期末自习室推荐")
        await _seed(admin_user.id, content="今天天气真好")
        r = await client.get("/api/v1/posts/search?q=自习室")
        assert r.status_code == 200
        items = r.json()["data"]["items"]
        assert len(items) == 1
        assert "自习室" in items[0]["content"]

    @pytest.mark.asyncio
    async def test_search_no_match(self, client: AsyncClient, admin_user: User):
        await _seed(admin_user.id, content="今天天气真好")
        r = await client.get("/api/v1/posts/search?q=不存在的关键词xyz")
        assert r.json()["data"]["items"] == []

    @pytest.mark.asyncio
    async def test_search_requires_q(self, client: AsyncClient):
        """q 为空 -> 422"""
        r = await client.get("/api/v1/posts/search")
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_search_excludes_ads(self, client: AsyncClient, admin_user: User):
        await _seed(admin_user.id, content="促销自习室", post_type="advertisement")
        r = await client.get("/api/v1/posts/search?q=自习室")
        assert all(i["post_type"] != "advertisement" for i in r.json()["data"]["items"])
