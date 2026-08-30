"""帖子分类（category）测试：创建带分类、按分类过滤。"""

import pytest
from httpx import AsyncClient

from app.models.user import User
from app.utils.security import create_access_token
from tests.conftest import TestSession, auth_header


def _token(u: User) -> str:
    return create_access_token({"sub": str(u.id), "role": u.role})


async def _seed_cat(user_id, content, category, post_type="general", status=1):
    from app.models.post import Post
    async with TestSession() as db:
        p = Post(user_id=user_id, post_type=post_type, category=category, content=content, status=status)
        db.add(p)
        await db.commit()
        await db.refresh(p)
        return p


class TestCategory:
    @pytest.mark.asyncio
    async def test_create_with_category(self, client: AsyncClient, admin_user: User):
        """admin 发帖带 category，响应回带 category"""
        r = await client.post("/api/v1/posts", json={
            "post_type": "general", "category": "表白墙", "content": "测试分类",
        }, headers=auth_header(_token(admin_user)))
        assert r.status_code == 200
        assert r.json()["data"]["status"] == 1  # admin 直通
        pid = r.json()["data"]["post_id"]
        d = await client.get(f"/api/v1/posts/{pid}")
        assert d.json()["data"]["category"] == "表白墙"

    @pytest.mark.asyncio
    async def test_filter_by_category(self, client: AsyncClient, admin_user: User):
        await _seed_cat(admin_user.id, "表白1", "表白墙")
        await _seed_cat(admin_user.id, "二手1", "二手市场")
        await _seed_cat(admin_user.id, "表白2", "表白墙")
        r = await client.get("/api/v1/posts?category=表白墙")
        items = r.json()["data"]["items"]
        assert len(items) == 2
        assert all(i["category"] == "表白墙" for i in items)

    @pytest.mark.asyncio
    async def test_category_excludes_ads(self, client: AsyncClient, admin_user: User, student_user: User):
        """分类过滤时不置顶广告"""
        await _seed_cat(admin_user.id, content="广告", category=None, post_type="advertisement", status=1)
        await _seed_cat(student_user.id, "表白帖", "表白墙", status=1)
        r = await client.get("/api/v1/posts?category=表白墙")
        items = r.json()["data"]["items"]
        assert len(items) == 1
        assert all(i["post_type"] != "advertisement" for i in items)

    @pytest.mark.asyncio
    async def test_no_category_excludes_advertisement(self, client: AsyncClient, admin_user: User):
        """无分类时返回全部普通帖，广告帖不混入（轮播位由 Banner 表承接）"""
        await _seed_cat(admin_user.id, content="普通", category="校园广场", status=1)
        await _seed_cat(admin_user.id, content="广告", category=None, post_type="advertisement", status=1)
        r = await client.get("/api/v1/posts")
        items = r.json()["data"]["items"]
        assert [it["content"] for it in items] == ["普通"]
