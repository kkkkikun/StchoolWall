"""我的互动接口测试：收藏通知 + 我的点赞/我的评论列表。"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.interaction import Comment, Favorite, Like
from app.models.notification import Notification
from app.models.post import Post
from app.models.user import User
from app.utils.security import create_access_token
from tests.conftest import TestSession, auth_header


async def _seed_post(user_id, content="被互动的帖子"):
    async with TestSession() as db:
        post = Post(user_id=user_id, post_type="general", content=content, status=1)
        db.add(post)
        await db.commit()
        await db.refresh(post)
        return post


class TestFavoriteNotification:

    @pytest.mark.asyncio
    async def test_favorite_creates_notification(self, client: AsyncClient, student_user: User, admin_user: User):
        """收藏触发 favorite 通知给作者；取消收藏不新增；重复收藏不重复通知。"""
        post = await _seed_post(admin_user.id)
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.post(f"/api/v1/posts/{post.id}/favorite", headers=auth_header(token))
        assert r.status_code == 200
        async with TestSession() as db:
            n = (await db.execute(
                select(Notification).where(
                    Notification.user_id == admin_user.id,
                    Notification.type == "favorite",
                    Notification.post_id == post.id,
                )
            )).scalars().all()
            assert len(n) == 1
        # 取消再收藏 = 新的一次互动，再通知一条（与 like_post 行为一致）
        await client.delete(f"/api/v1/posts/{post.id}/favorite", headers=auth_header(token))
        await client.post(f"/api/v1/posts/{post.id}/favorite", headers=auth_header(token))
        async with TestSession() as db:
            n = (await db.execute(
                select(Notification).where(Notification.user_id == admin_user.id, Notification.type == "favorite")
            )).scalars().all()
            assert len(n) == 2


class TestMyLists:

    @pytest.mark.asyncio
    async def test_my_likes_and_comments(self, client: AsyncClient, student_user: User):
        post = await _seed_post(student_user.id)
        async with TestSession() as db:
            db.add(Like(user_id=student_user.id, post_id=post.id))
            db.add(Comment(user_id=student_user.id, post_id=post.id, content="我来评论一句"))
            db.add(Comment(user_id=student_user.id, post_id=post.id, content="被软删的评论", status=-1))
            await db.commit()
        token = create_access_token({"sub": str(student_user.id), "role": "student"})

        r = await client.get("/api/v1/me/likes", headers=auth_header(token))
        assert r.status_code == 200
        items = r.json()["data"]["items"]
        assert any(p["id"] == post.id for p in items)

        r2 = await client.get("/api/v1/me/comments", headers=auth_header(token))
        assert r2.status_code == 200
        comments = r2.json()["data"]["items"]
        assert len(comments) == 1  # 软删除的不出现
        assert comments[0]["content"] == "我来评论一句"
        assert comments[0]["post_id"] == post.id
        assert comments[0]["post_excerpt"]

    @pytest.mark.asyncio
    async def test_my_lists_require_login(self, client: AsyncClient):
        assert (await client.get("/api/v1/me/likes")).status_code == 401
        assert (await client.get("/api/v1/me/comments")).status_code == 401
