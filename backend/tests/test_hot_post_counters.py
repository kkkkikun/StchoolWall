"""热点帖单行写锁回归测试。

背景（docs/production/capacity.md）：详情页浏览数自增同步写 posts 行，与点赞路径的
`SELECT ... FOR UPDATE` 争热点帖同一 tuple，PostgreSQL 记录到同一行上最长 38 个进程的
锁等待队列，burst 场景读 p95 2743.72ms / 写 p95 4063.85ms。

本文件固定三条行为：
1. 详情页浏览不再写 posts 行（外部持锁时详情请求仍能立即返回）；
2. 浏览计数进入异步聚合缓冲，折叠后与浏览次数一致；
3. 点赞/取消赞不再锁 posts 行，计数与 likes 表始终一致。
"""
import asyncio
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update

from app.models.interaction import Like
from app.models.post import Post
from app.models.user import User
from app.models.view_counter import PostViewCounter
from app.services.view_counters import flush_post_view_counters
from app.utils.security import create_access_token
from tests.conftest import TestSession, auth_header

pytestmark = pytest.mark.asyncio

LOCK_TIMEOUT_SECONDS = 10


async def _mk_user(prefix: str) -> User:
    async with TestSession() as db:
        u = User(
            openid=f"{prefix}_{uuid.uuid4().hex[:10]}",
            nickname=prefix,
            role="student",
            is_verified=True,
        )
        db.add(u)
        await db.commit()
        await db.refresh(u)
        return u


async def _mk_post(user_id: uuid.UUID) -> int:
    async with TestSession() as db:
        p = Post(user_id=user_id, post_type="general", content="热点帖锁回归目标帖", status=1)
        db.add(p)
        await db.commit()
        await db.refresh(p)
        return p.id


def _headers(user: User) -> dict:
    return auth_header(create_access_token({"sub": str(user.id), "role": user.role}))


class TestDetailViewDoesNotLockPostRow:
    async def test_detail_succeeds_while_post_row_is_locked(self, client: AsyncClient):
        """外部事务锁住 posts 行时，详情请求不得被阻塞（浏览数不再写 posts 行）。"""
        author = await _mk_user("hot_author")
        viewer = await _mk_user("hot_viewer")
        post_id = await _mk_post(author.id)

        async with TestSession() as locker:
            # FOR SHARE 与计数 UPDATE（FOR NO KEY UPDATE）互斥：详情页若再写 posts 行必然被挡住；
            # 浏览足迹外键检查只取 KEY SHARE，与 FOR SHARE 兼容，故新实现不会等待。
            await locker.execute(
                select(Post).where(Post.id == post_id).with_for_update(read=True)
            )
            task = asyncio.create_task(
                client.get(f"/api/v1/posts/{post_id}", headers=_headers(viewer))
            )
            done, _ = await asyncio.wait({task}, timeout=LOCK_TIMEOUT_SECONDS)
            if not done:
                task.cancel()
                raise AssertionError(
                    "详情请求被 posts 行锁阻塞：浏览数仍在同步写 posts 行（热点帖单行写锁回归）"
                )
            response = task.result()
            assert response.status_code == 200

    async def test_like_succeeds_for_hot_post_under_lock_pressure(self, client: AsyncClient):
        """点赞在热点帖上仍是「一次原子自增」，不因行锁排队而报错。"""
        author = await _mk_user("hot_author2")
        likers = [await _mk_user(f"hot_liker{i}") for i in range(4)]
        post_id = await _mk_post(author.id)

        responses = await asyncio.gather(*[
            client.post(f"/api/v1/posts/{post_id}/like", headers=_headers(u)) for u in likers
        ])
        assert all(r.status_code == 200 for r in responses)

        async with TestSession() as db:
            stored = (
                await db.execute(select(Post.like_count).where(Post.id == post_id))
            ).scalar_one()
        assert stored == len(likers)


class TestAsyncViewAggregation:
    async def test_views_go_to_counter_and_flush_into_post(self, client: AsyncClient):
        author = await _mk_user("view_author")
        viewers = [await _mk_user(f"view_user{i}") for i in range(5)]
        post_id = await _mk_post(author.id)

        for viewer in viewers:
            r = await client.get(f"/api/v1/posts/{post_id}", headers=_headers(viewer))
            assert r.status_code == 200

        async with TestSession() as db:
            pending = (
                await db.execute(
                    select(PostViewCounter.views).where(PostViewCounter.post_id == post_id)
                )
            ).scalar_one()
            stored = (
                await db.execute(select(Post.view_count).where(Post.id == post_id))
            ).scalar_one()
        assert pending == len(viewers)
        assert stored == 0  # 折叠前 posts 行不承载浏览计数

        async with TestSession() as db:
            folded = await flush_post_view_counters(db)
        assert folded == 1

        async with TestSession() as db:
            stored = (
                await db.execute(select(Post.view_count).where(Post.id == post_id))
            ).scalar_one()
            pending = (
                await db.execute(
                    select(PostViewCounter.views).where(PostViewCounter.post_id == post_id)
                )
            ).scalar_one_or_none()
        assert stored == len(viewers)
        assert not pending

    async def test_detail_reports_pending_views(self, client: AsyncClient):
        """详情返回「已聚合值 + 待聚合增量」，浏览后立即可见。"""
        author = await _mk_user("view_author2")
        viewer = await _mk_user("view_user_single")
        post_id = await _mk_post(author.id)

        r = await client.get(f"/api/v1/posts/{post_id}", headers=_headers(viewer))
        assert r.json()["data"]["view_count"] == 1

    async def test_concurrent_views_are_not_lost(self, client: AsyncClient):
        author = await _mk_user("view_author3")
        viewers = [await _mk_user(f"view_conc{i}") for i in range(10)]
        post_id = await _mk_post(author.id)

        responses = await asyncio.gather(*[
            client.get(f"/api/v1/posts/{post_id}", headers=_headers(v)) for v in viewers
        ])
        assert all(r.status_code == 200 for r in responses)

        async with TestSession() as db:
            pending = (
                await db.execute(
                    select(PostViewCounter.views).where(PostViewCounter.post_id == post_id)
                )
            ).scalar_one()
        assert pending == len(viewers)


class TestLikeCountConsistency:
    async def test_like_count_matches_likes_table(self, client: AsyncClient):
        author = await _mk_user("like_author")
        post_id = await _mk_post(author.id)
        likers = [await _mk_user(f"like_user{i}") for i in range(8)]

        await asyncio.gather(*[
            client.post(f"/api/v1/posts/{post_id}/like", headers=_headers(u)) for u in likers
        ])
        # 一半取消赞
        await asyncio.gather(*[
            client.delete(f"/api/v1/posts/{post_id}/like", headers=_headers(u))
            for u in likers[:4]
        ])

        async with TestSession() as db:
            stored = (
                await db.execute(select(Post.like_count).where(Post.id == post_id))
            ).scalar_one()
            actual = (
                await db.execute(
                    select(func.count()).select_from(Like).where(Like.post_id == post_id)
                )
            ).scalar_one()
        assert stored == actual == 4

    async def test_unlike_never_goes_below_zero(self, client: AsyncClient):
        author = await _mk_user("like_author2")
        viewer = await _mk_user("like_user_zero")
        post_id = await _mk_post(author.id)

        r = await client.delete(f"/api/v1/posts/{post_id}/like", headers=_headers(viewer))
        assert r.status_code == 200
        assert r.json()["data"]["like_count"] == 0

        async with TestSession() as db:
            stored = (
                await db.execute(select(Post.like_count).where(Post.id == post_id))
            ).scalar_one()
        assert stored == 0

    async def test_hide_post_keeps_like_count_consistent(self, client: AsyncClient):
        """帖子被隐藏时计数不得漂移（计数语句不再依赖 posts.status）。"""
        author = await _mk_user("like_author3")
        liker = await _mk_user("like_user_hide")
        post_id = await _mk_post(author.id)

        await client.post(f"/api/v1/posts/{post_id}/like", headers=_headers(liker))
        async with TestSession() as db:
            await db.execute(update(Post).where(Post.id == post_id).values(status=0))
            await db.commit()

        async with TestSession() as db:
            stored = (
                await db.execute(select(Post.like_count).where(Post.id == post_id))
            ).scalar_one()
            actual = (
                await db.execute(
                    select(func.count()).select_from(Like).where(Like.post_id == post_id)
                )
            ).scalar_one()
        assert stored == actual == 1
