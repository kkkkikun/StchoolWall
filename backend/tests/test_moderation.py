"""异步审核任务测试：BackgroundTasks 审核帖子图片"""

import pytest
from httpx import AsyncClient

from app.models.post import Post
from app.models.user import User
from app.utils.security import create_access_token
from tests.conftest import TestSession, auth_header


async def _get_post_status(post_id: int) -> int:
    async with TestSession() as db:
        from sqlalchemy import select
        result = await db.execute(select(Post).where(Post.id == post_id))
        post = result.scalar_one_or_none()
        return post.status if post else None


# ============================================================
# POST /api/v1/posts — 后台审核任务
# ============================================================


class TestModerationBackgroundTask:

    @pytest.mark.asyncio
    async def test_student_post_triggers_moderation(self, client: AsyncClient, student_user: User):
        """student 发帖触发后台审核，status 从 0 变为 1"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.post(
            "/api/v1/posts",
            json={
                "post_type": "general",
                "content": "测试帖",
                "images": ["https://img.test.com/1.jpg"],
            },
            headers=auth_header(token),
        )
        assert r.status_code == 200
        post_id = r.json()["data"]["post_id"]

        # 等待后台任务完成（BackgroundTasks 在响应后执行）
        import asyncio
        await asyncio.sleep(0.2)

        # 验证状态已更新为 1
        status = await _get_post_status(post_id)
        assert status == 1

    @pytest.mark.asyncio
    async def test_post_without_images_passes_directly(self, client: AsyncClient, student_user: User):
        """无图片帖子直接通过"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.post(
            "/api/v1/posts",
            json={
                "post_type": "general",
                "content": "纯文字帖",
            },
            headers=auth_header(token),
        )
        assert r.status_code == 200
        post_id = r.json()["data"]["post_id"]

        import asyncio
        await asyncio.sleep(0.2)

        status = await _get_post_status(post_id)
        assert status == 1

    @pytest.mark.asyncio
    async def test_admin_post_skips_moderation(self, client: AsyncClient, admin_user: User):
        """admin 发帖直接 status=1，不触发后台任务"""
        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        r = await client.post(
            "/api/v1/posts",
            json={
                "post_type": "general",
                "content": "管理员帖",
            },
            headers=auth_header(token),
        )
        assert r.status_code == 200
        post_id = r.json()["data"]["post_id"]

        # admin 发帖立即 status=1
        status = await _get_post_status(post_id)
        assert status == 1

    @pytest.mark.asyncio
    async def test_moderation_failure_blocks_post(self, client: AsyncClient, student_user: User):
        """模拟审核失败，帖子被封禁"""
        from unittest.mock import patch

        # Mock 审核失败
        with patch("app.services.moderation.check_images", return_value=False):
            token = create_access_token({"sub": str(student_user.id), "role": "student"})
            r = await client.post(
                "/api/v1/posts",
                json={
                    "post_type": "general",
                    "content": "违规内容",
                    "images": ["https://img.test.com/bad.jpg"],
                },
                headers=auth_header(token),
            )
            assert r.status_code == 200
            post_id = r.json()["data"]["post_id"]

            import asyncio
            await asyncio.sleep(0.2)

            status = await _get_post_status(post_id)
            assert status == -1  # 封禁

    @pytest.mark.asyncio
    async def test_text_moderation(self, client: AsyncClient, student_user: User):
        """文本审核（可选）"""
        from unittest.mock import patch

        with patch("app.services.moderation.check_text", return_value=False):
            token = create_access_token({"sub": str(student_user.id), "role": "student"})
            r = await client.post(
                "/api/v1/posts",
                json={
                    "post_type": "general",
                    "content": "违禁文本",
                },
                headers=auth_header(token),
            )
            assert r.status_code == 200
            post_id = r.json()["data"]["post_id"]

            import asyncio
            await asyncio.sleep(0.2)

            status = await _get_post_status(post_id)
            assert status == -1
