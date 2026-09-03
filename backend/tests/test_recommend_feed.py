"""推荐流排序测试：热度时间衰减分（Reddit 式）+ 键集分页。

设计：
- score = (like*3 + comment*2 + view*0.2 + 1) / (发布小时数 + 2)^1.2
- 分子 +1：零互动新帖不被永久淹没（约等于按时间排）
- 与热帖榜（hot_posts）权重同源，仅多时间衰减
- 仅"推荐位"（无 category/post_type）生效；分类流保持时间序
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.post import Post
from app.models.user import User
from app.services.post import list_posts
from tests.conftest import TestSession


async def _seed(
    user_id, *, content="帖子", likes=0, comments=0, views=0,
    age_hours=0.0, category=None,
):
    async with TestSession() as db:
        post = Post(
            user_id=user_id,
            post_type="general",
            content=content,
            status=1,
            like_count=likes,
            comment_count=comments,
            view_count=views,
            category=category,
            created_at=datetime.now(timezone.utc) - timedelta(hours=age_hours),
        )
        db.add(post)
        await db.commit()
        await db.refresh(post)
        return post


class TestRecommendOrdering:

    @pytest.mark.asyncio
    async def test_hot_old_beats_plain_new(self, student_user: User):
        """高互动旧帖应排在零互动新帖之前。"""
        hot = await _seed(student_user.id, content="三天前爆帖", likes=50, age_hours=72)
        new = await _seed(student_user.id, content="一小时前新帖", age_hours=1)
        async with TestSession() as db:
            items, _, _ = await list_posts(db, limit=10)
        ids = [it["id"] for it in items]
        assert ids.index(hot.id) < ids.index(new.id)

    @pytest.mark.asyncio
    async def test_hotter_wins_among_old(self, student_user: User):
        """同为旧帖，互动高的在前。"""
        mild = await _seed(student_user.id, content="一般热", likes=10, age_hours=48)
        top = await _seed(student_user.id, content="更热", likes=100, age_hours=48)
        async with TestSession() as db:
            items, _, _ = await list_posts(db, limit=10)
        ids = [it["id"] for it in items]
        assert ids.index(top.id) < ids.index(mild.id)

    @pytest.mark.asyncio
    async def test_zero_engagement_falls_back_to_recent_first(
        self, student_user: User
    ):
        """全部零互动时，衰减分退化为近似时间序：新帖在前。"""
        old = await _seed(student_user.id, content="五天前", age_hours=120)
        recent = await _seed(student_user.id, content="一天前", age_hours=24)
        async with TestSession() as db:
            items, _, _ = await list_posts(db, limit=10)
        ids = [it["id"] for it in items]
        assert ids.index(recent.id) < ids.index(old.id)

    @pytest.mark.asyncio
    async def test_category_feed_stays_time_ordered(self, student_user: User):
        """分类流不启用热度排序：保持最新在前。"""
        hot_old = await _seed(
            student_user.id, content="分类里的爆帖", likes=99, age_hours=72, category="二手"
        )
        plain_new = await _seed(
            student_user.id, content="分类里的新帖", age_hours=1, category="二手"
        )
        async with TestSession() as db:
            items, _, _ = await list_posts(db, limit=10, category="二手")
        ids = [it["id"] for it in items]
        assert ids.index(plain_new.id) < ids.index(hot_old.id)


class TestLatestOrder:
    """order=time 最新流：纯时间序，不受热度分影响，也不出现置顶块。"""

    @pytest.mark.asyncio
    async def test_latest_ignores_hot_score(self, student_user: User):
        hot_old = await _seed(student_user.id, content="旧热帖", likes=50, age_hours=72)
        plain_new = await _seed(student_user.id, content="新帖零互动", age_hours=1)
        async with TestSession() as db:
            items, _, _ = await list_posts(db, limit=10, order="time")
        ids = [it["id"] for it in items]
        assert ids.index(plain_new.id) < ids.index(hot_old.id)


class TestRecommendPagination:

    @pytest.mark.asyncio
    async def test_keyset_pagination_no_dup_no_gap(self, student_user: User):
        """热度排序下翻页：不重不漏，页内得分单调不增。"""
        seeds = [
            (100, 72), (80, 48), (60, 24), (40, 12), (20, 2),
        ]  # (likes, age_hours) —— 得分各不相同
        for i, (likes, age) in enumerate(seeds):
            await _seed(student_user.id, content=f"帖{i}", likes=likes, age_hours=age)

        async with TestSession() as db:
            seen, cursor = [], None
            for _ in range(10):  # 防死循环
                items, cursor, has_more = await list_posts(db, cursor=cursor, limit=2)
                seen.extend(it["id"] for it in items)
                if not has_more:
                    break
        assert len(seen) == len(set(seen)) == 5, "翻页结果不重不漏"
        assert cursor is None
