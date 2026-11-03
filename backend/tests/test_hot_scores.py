"""帖子列表类查询的扫描面收敛：榜单预计算 + 搜索索引。

覆盖两条路径：
- 推荐流 `/api/v1/posts`（不带 order）：热度分由 worker 周期预计算落表，
  查询走 (score, id) 索引扫描；榜单缺失或过期时退回实时计算，结果口径一致。
- 搜索 `/api/v1/posts/search?q=…`：`content ILIKE '%q%'` 的子串匹配语义不变
  （大小写不敏感、通配符仍被转义），只是走 pg_trgm GIN 索引。
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text, update

from app.models.hot_score import PostHotScore, PostHotScoreState
from app.models.post import Post
from app.models.user import User
from app.services.hot_scores import (
    HOT_SCORE_STALE_SECONDS,
    refresh_hot_scores,
)
from app.services.post import list_posts, search_posts
from tests.conftest import TestSession


async def _seed(
    user_id, *, content="帖子", likes=0, comments=0, views=0,
    age_hours=0.0, status=1, pinned=False, post_type="general",
):
    async with TestSession() as db:
        post = Post(
            user_id=user_id,
            post_type=post_type,
            content=content,
            status=status,
            is_pinned=pinned,
            like_count=likes,
            comment_count=comments,
            view_count=views,
            created_at=datetime.now(timezone.utc) - timedelta(hours=age_hours),
        )
        db.add(post)
        await db.commit()
        await db.refresh(post)
        return post


class TestLeaderboardRefresh:

    @pytest.mark.asyncio
    async def test_refresh_records_state_and_scores(self, student_user: User):
        """刷新后写入状态行与每个候选帖的热度分。"""
        post = await _seed(student_user.id, content="爆帖", likes=30, age_hours=5)
        async with TestSession() as db:
            count = await refresh_hot_scores(db)
        assert count == 1
        async with TestSession() as db:
            state = (await db.execute(
                select(PostHotScoreState).where(PostHotScoreState.id == 1)
            )).scalar_one()
            score = (await db.execute(
                select(PostHotScore.score).where(PostHotScore.post_id == post.id)
            )).scalar_one()
        assert state.post_count == 1
        assert state.computed_at is not None
        # 热度分公式：互动加权 / 时间衰减，30 赞 5 小时前约 (30*3+1)/(5+2)^1.2
        expected = (30 * 3 + 1) / (5 + 2) ** 1.2
        assert abs(score - expected) < 0.05

    @pytest.mark.asyncio
    async def test_only_eligible_posts_are_scored(self, student_user: User):
        """待审、置顶、广告帖不进榜单。"""
        visible = await _seed(student_user.id, content="正常帖")
        pending = await _seed(student_user.id, content="待审帖", status=0)
        pinned = await _seed(student_user.id, content="置顶帖", pinned=True)
        ad = await _seed(student_user.id, content="广告帖", post_type="advertisement")
        async with TestSession() as db:
            assert await refresh_hot_scores(db) == 1
        async with TestSession() as db:
            scored = set((await db.execute(select(PostHotScore.post_id))).scalars())
        assert scored == {visible.id}
        assert pending.id not in scored
        assert pinned.id not in scored
        assert ad.id not in scored

    @pytest.mark.asyncio
    async def test_hidden_post_is_dropped_from_leaderboard(self, student_user: User):
        """帖子被隐藏后，下一轮刷新把它从榜单里清掉。"""
        post = await _seed(student_user.id, content="先可见")
        async with TestSession() as db:
            await refresh_hot_scores(db)
        async with TestSession() as db:
            await db.execute(update(Post).where(Post.id == post.id).values(status=2))
            await db.commit()
            await refresh_hot_scores(db)
        async with TestSession() as db:
            scored = set((await db.execute(select(PostHotScore.post_id))).scalars())
        assert scored == set()


class TestRecommendFeedUsesLeaderboard:

    @pytest.mark.asyncio
    async def test_feed_order_follows_leaderboard(self, student_user: User):
        """榜单里的分决定推荐流顺序（而不是实时公式）。"""
        hot = await _seed(student_user.id, content="互动高", likes=100, age_hours=48)
        plain = await _seed(student_user.id, content="零互动", age_hours=1)
        async with TestSession() as db:
            await refresh_hot_scores(db)
            # 人为把零互动帖的榜单分调高：若查询真的走榜单，顺序会反转
            await db.execute(
                update(PostHotScore).where(PostHotScore.post_id == plain.id)
                .values(score=9999.0)
            )
            await db.commit()
            items, _, _ = await list_posts(db, limit=10)
        ids = [it["id"] for it in items]
        assert ids.index(plain.id) < ids.index(hot.id)

    @pytest.mark.asyncio
    async def test_fallback_when_leaderboard_missing(self, student_user: User):
        """榜单缺失（worker 未运行）时退回实时计算，排序仍按热度分。"""
        hot = await _seed(student_user.id, content="互动高", likes=100, age_hours=48)
        plain = await _seed(student_user.id, content="零互动", age_hours=1)
        async with TestSession() as db:
            items, _, _ = await list_posts(db, limit=10)
        ids = [it["id"] for it in items]
        assert ids.index(hot.id) < ids.index(plain.id)

    @pytest.mark.asyncio
    async def test_fallback_when_leaderboard_stale(self, student_user: User):
        """榜单过期（worker 停了）时退回实时计算，结果依然正确。"""
        hot = await _seed(student_user.id, content="互动高", likes=100, age_hours=48)
        plain = await _seed(student_user.id, content="零互动", age_hours=1)
        async with TestSession() as db:
            await refresh_hot_scores(db)
            stale = datetime.now(timezone.utc) - timedelta(seconds=HOT_SCORE_STALE_SECONDS + 60)
            await db.execute(
                update(PostHotScoreState).where(PostHotScoreState.id == 1)
                .values(computed_at=stale)
            )
            await db.commit()
            items, _, _ = await list_posts(db, limit=10)
        ids = [it["id"] for it in items]
        assert ids.index(hot.id) < ids.index(plain.id)

    @pytest.mark.asyncio
    async def test_leaderboard_feed_returns_all_eligible_posts(self, student_user: User):
        """走榜单的推荐流不丢帖：候选集与实时路径一致。"""
        posts = [await _seed(student_user.id, content=f"帖{i}", likes=i * 10, age_hours=i) for i in range(4)]
        async with TestSession() as db:
            await refresh_hot_scores(db)
            items, _, _ = await list_posts(db, limit=50)
        assert sorted(it["id"] for it in items) == sorted(p.id for p in posts)

    @pytest.mark.asyncio
    async def test_keyset_pagination_over_leaderboard(self, student_user: User):
        """走榜单的推荐流翻页：不重不漏。"""
        for i in range(5):
            await _seed(student_user.id, content=f"帖{i}", likes=(5 - i) * 10, age_hours=i)
        async with TestSession() as db:
            await refresh_hot_scores(db)
            seen, cursor = [], None
            for _ in range(10):
                items, cursor, has_more = await list_posts(db, cursor=cursor, limit=2)
                seen.extend(it["id"] for it in items)
                if not has_more:
                    break
        assert len(seen) == 5
        assert len(set(seen)) == 5

    @pytest.mark.asyncio
    async def test_cursor_missing_from_leaderboard_keeps_paging(self, student_user: User):
        """游标帖被隐藏（不在榜单里）时，翻页不中断。"""
        first = await _seed(student_user.id, content="第一页", likes=50, age_hours=1)
        second = await _seed(student_user.id, content="第二页", likes=40, age_hours=2)
        third = await _seed(student_user.id, content="第三页", likes=30, age_hours=3)
        async with TestSession() as db:
            await refresh_hot_scores(db)
            items, cursor, has_more = await list_posts(db, limit=1)
            assert items[0]["id"] == first.id
            assert has_more is True
            await db.execute(update(Post).where(Post.id == first.id).values(status=2))
            await db.commit()
            await refresh_hot_scores(db)
            items2, _, _ = await list_posts(db, cursor=cursor, limit=10)
        ids = [it["id"] for it in items2]
        assert second.id in ids and third.id in ids


class TestSearchSemanticsUnchanged:

    @pytest.mark.asyncio
    async def test_search_is_case_insensitive_substring(self, student_user: User):
        """搜索仍是大小写不敏感的子串匹配。"""
        post = await _seed(student_user.id, content="Campus Course 拼车")
        async with TestSession() as db:
            items, _, _ = await search_posts(db, "campus", limit=10)
            upper, _, _ = await search_posts(db, "COURSE", limit=10)
            middle, _, _ = await search_posts(db, "pus Cou", limit=10)
        assert [it["id"] for it in items] == [post.id]
        assert [it["id"] for it in upper] == [post.id]
        assert [it["id"] for it in middle] == [post.id]

    @pytest.mark.asyncio
    async def test_search_escapes_wildcards(self, student_user: User):
        """通配符仍被转义：搜 `%` 不会命中全部帖子。"""
        await _seed(student_user.id, content="普通帖")
        await _seed(student_user.id, content="含百分号 100% 的帖")
        async with TestSession() as db:
            items, _, _ = await search_posts(db, "%", limit=50)
        assert len(items) == 1
        assert items[0]["content"] == "含百分号 100% 的帖"

    @pytest.mark.asyncio
    async def test_trigram_index_exists(self):
        """pg_trgm GIN 索引已建（迁移与模型元数据一致）。"""
        async with TestSession() as db:
            rows = (await db.execute(text(
                "SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_posts_content_trgm'"
            ))).all()
        assert rows, "ix_posts_content_trgm 缺失"
        assert "gin_trgm_ops" in rows[0][0]
