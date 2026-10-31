from tests.production_helpers import approve_comments
"""并发计数回归测试：点赞/评论在并发写时不得丢失计数或抛 500。

背景：计数曾是 read-modify-write（post.like_count = post.like_count + 1），
并发下会互相覆盖；点赞/收藏也曾是 check-then-insert，并发下会撞唯一约束。
"""
import asyncio
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.interaction import Comment, Like
from app.models.post import Post
from app.models.user import User
from app.utils.security import create_access_token
from tests.conftest import TestSession

pytestmark = pytest.mark.asyncio


async def _mk_verified_user(prefix: str) -> User:
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
        p = Post(user_id=user_id, post_type="general", content="并发计数目标帖", status=1)
        db.add(p)
        await db.commit()
        await db.refresh(p)
        return p.id


def _headers(user: User) -> dict:
    token = create_access_token({"sub": str(user.id), "role": user.role})
    return {"Authorization": f"Bearer {token}"}


class TestConcurrentCounts:
    async def test_distinct_users_like_keeps_count(self, client: AsyncClient):
        author = await _mk_verified_user("author")
        pid = await _mk_post(author.id)
        likers = [await _mk_verified_user(f"liker{i}") for i in range(8)]

        resps = await asyncio.gather(*[
            client.post(f"/api/v1/posts/{pid}/like", headers=_headers(u))
            for u in likers
        ])
        assert all(r.status_code == 200 for r in resps)

        detail = (await client.get(f"/api/v1/posts/{pid}")).json()["data"]
        assert detail["like_count"] == 8

    async def test_same_user_like_is_idempotent_under_concurrency(self, client: AsyncClient):
        author = await _mk_verified_user("author2")
        pid = await _mk_post(author.id)
        liker = await _mk_verified_user("liker_solo")

        resps = await asyncio.gather(*[
            client.post(f"/api/v1/posts/{pid}/like", headers=_headers(liker))
            for _ in range(20)
        ])
        assert all(r.status_code == 200 for r in resps)

        detail = (await client.get(f"/api/v1/posts/{pid}")).json()["data"]
        assert detail["like_count"] == 1

        async with TestSession() as db:
            rows = (await db.execute(select(Like).where(Like.post_id == pid))).scalars().all()
            assert len(rows) == 1

    async def test_distinct_users_comment_keeps_count(self, client: AsyncClient):
        author = await _mk_verified_user("author3")
        pid = await _mk_post(author.id)
        commenters = [await _mk_verified_user(f"commenter{i}") for i in range(8)]

        resps = await asyncio.gather(*[
            client.post(
                f"/api/v1/posts/{pid}/comments",
                json={"content": f"并发评论{i}"},
                headers=_headers(u),
            )
            for i, u in enumerate(commenters)
        ])
        assert all(r.status_code == 200 for r in resps)

        assert all(r.json()["data"]["status"] == 0 for r in resps)
        await approve_comments()
        detail = (await client.get(f"/api/v1/posts/{pid}")).json()["data"]
        assert detail["comment_count"] == 8

        async with TestSession() as db:
            rows = (await db.execute(select(Comment).where(Comment.post_id == pid, Comment.status == 1))).scalars().all()
            assert len(rows) == 8
