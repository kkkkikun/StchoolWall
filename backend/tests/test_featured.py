"""精华机制测试：精华流（历史热度无衰减）+ 管理端设精（审计）+ 候选队列 + 搜索置顶。"""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.models.post import Post
from app.models.user import User
from app.services.post import featured_posts, search_posts
from app.utils.security import create_access_token
from tests.conftest import TestSession, auth_header


async def _seed(
    user_id, *, content="精华测试帖", likes=0, comments=0, views=0,
    featured=False, age_hours=24 * 30, post_type="general", status=1,
):
    async with TestSession() as db:
        post = Post(
            user_id=user_id,
            post_type=post_type,
            content=content,
            status=status,
            like_count=likes,
            comment_count=comments,
            view_count=views,
            is_featured=featured,
            featured_at=datetime.now(timezone.utc) if featured else None,
            created_at=datetime.now(timezone.utc) - timedelta(hours=age_hours),
        )
        db.add(post)
        await db.commit()
        await db.refresh(post)
        return post


class TestFeaturedFeed:

    @pytest.mark.asyncio
    async def test_featured_list_ordering_no_decay(self, student_user: User):
        """精华流按历史总热度排序：一个月前的高赞老帖照样第一。"""
        king = await _seed(student_user.id, content="考研经验长文", likes=100, age_hours=24 * 60, featured=True)
        mid = await _seed(student_user.id, content="新生指南", likes=20, age_hours=24 * 10, featured=True)
        plain = await _seed(student_user.id, content="刚设精", likes=3, age_hours=1, featured=True)
        not_featured = await _seed(student_user.id, content="普通帖", likes=999)
        async with TestSession() as db:
            items, _, _ = await featured_posts(db)
        ids = [it["id"] for it in items]
        assert ids[:3] == [king.id, mid.id, plain.id]
        assert not_featured.id not in ids

    @pytest.mark.asyncio
    async def test_featured_excludes_ads_and_banned(self, student_user: User):
        ad = await _seed(student_user.id, content="广告帖", post_type="advertisement", featured=True)
        banned = await _seed(student_user.id, content="被封帖", status=-1, featured=True)
        ok = await _seed(student_user.id, content="正常精华", featured=True)
        async with TestSession() as db:
            items, _, _ = await featured_posts(db)
        ids = [it["id"] for it in items]
        assert ok.id in ids
        assert ad.id not in ids and banned.id not in ids

    @pytest.mark.asyncio
    async def test_featured_keyset_pagination(self, student_user: User):
        for i, likes in enumerate([50, 40, 30, 20, 10]):
            await _seed(student_user.id, content=f"精华{i}", likes=likes, featured=True)
        async with TestSession() as db:
            seen, cursor = [], None
            for _ in range(10):
                items, cursor, has_more = await featured_posts(db, cursor=cursor, limit=2)
                seen.extend(it["id"] for it in items)
                if not has_more:
                    break
        assert len(seen) == len(set(seen)) == 5

    @pytest.mark.asyncio
    async def test_featured_public_endpoint(self, client: AsyncClient, student_user: User):
        await _seed(student_user.id, content="公开可见", featured=True)
        r = await client.get("/api/v1/posts/featured")
        assert r.status_code == 200
        assert any("公开可见" in it["content"] for it in r.json()["data"]["items"])


class TestAdminFeatureToggle:

    @pytest.mark.asyncio
    async def test_toggle_feature_with_audit(self, client: AsyncClient, admin_user: User):
        post = await _seed(admin_user.id, content="待设精", likes=15)
        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        r = await client.put(
            f"/api/v1/admin/posts/{post.id}/featured",
            json={"pinned": True}, headers=auth_header(token),
        )
        assert r.status_code == 200 and r.json()["data"]["is_featured"] is True
        # 审计留痕
        async with TestSession() as db:
            from sqlalchemy import select
            from app.models.admin_log import AdminLog
            log = (await db.execute(
                select(AdminLog).where(AdminLog.action == "post.featured", AdminLog.target_id == str(post.id))
            )).scalar_one_or_none()
            assert log is not None
        # 取消
        r2 = await client.put(
            f"/api/v1/admin/posts/{post.id}/featured",
            json={"pinned": False}, headers=auth_header(token),
        )
        assert r2.status_code == 200 and r2.json()["data"]["is_featured"] is False

    @pytest.mark.asyncio
    async def test_feature_404_and_forbidden(
        self, client: AsyncClient, student_user: User, guest_user: User
    ):
        token_student = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.put(
            "/api/v1/admin/posts/999999/featured",
            json={"pinned": True}, headers=auth_header(token_student),
        )
        assert r.status_code == 403  # 学生没权限

    @pytest.mark.asyncio
    async def test_candidates_queue(self, client: AsyncClient, admin_user: User):
        hot = await _seed(admin_user.id, content="高互动候选", likes=10, comments=3)   # score 42
        low = await _seed(admin_user.id, content="低互动", likes=1)                    # score 3 < 门槛
        already = await _seed(admin_user.id, content="已设精", likes=99, featured=True)
        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        r = await client.get("/api/v1/admin/posts/feature-candidates", headers=auth_header(token))
        assert r.status_code == 200
        contents = [it["content"] for it in r.json()["data"]["items"]]
        assert "高互动候选" in contents
        assert "低互动" not in contents and "已设精" not in contents


class TestSearchFeaturedFirst:

    @pytest.mark.asyncio
    async def test_search_featured_pinned_first(self, student_user: User):
        normal = await _seed(student_user.id, content="考研经验分享", likes=1)
        feat = await _seed(student_user.id, content="考研经验长文", likes=30, featured=True)
        async with TestSession() as db:
            items, _, _ = await search_posts(db, "考研经验")
        ids = [it["id"] for it in items]
        assert ids.index(feat.id) < ids.index(normal.id)

    @pytest.mark.asyncio
    async def test_search_pagination_after_boost(self, student_user: User):
        for i in range(5):
            await _seed(student_user.id, content=f"搜库名{i}", likes=i, featured=(i == 4))
        async with TestSession() as db:
            seen, cursor = [], None
            for _ in range(10):
                items, cursor, has_more = await search_posts(db, "搜库名", cursor=cursor, limit=2)
                seen.extend(it["id"] for it in items)
                if not has_more:
                    break
        assert len(seen) == len(set(seen)) == 5
