"""异步审核任务测试：BackgroundTasks 审核帖子图片

注意：BackgroundTasks 在 ASGI 测试环境中执行不完整。
完整的审核流程需要 E2E 测试或手动验证。
"""

import pytest
from httpx import AsyncClient

from app.models.user import User
from app.utils.security import create_access_token
from tests.conftest import auth_header


# ============================================================
# 审核工具函数测试（不依赖数据库）
# ============================================================


class TestModerationUtils:

    @pytest.mark.asyncio
    async def test_check_images_passes(self):
        """图片审核：未配置腾讯审核时进入人工队列"""
        from app.utils.moderation import check_images
        result = await check_images(["https://img.test.com/1.jpg"])
        assert result.verdict == "review"

    @pytest.mark.asyncio
    async def test_check_empty_images(self):
        """空图片列表通过"""
        from app.utils.moderation import check_images
        result = await check_images([])
        assert result.verdict == "pass"

    @pytest.mark.asyncio
    async def test_check_text_passes(self):
        """文本审核：未配置腾讯审核时进入人工队列"""
        from app.utils.moderation import check_text
        result = await check_text("正常内容", "openid_x")
        assert result.verdict == "review"


# ============================================================
# POST /api/v1/posts — 集成测试（验证状态设置）
# ============================================================


class TestModerationIntegration:

    @pytest.mark.asyncio
    async def test_admin_post_skips_moderation(self, client: AsyncClient, admin_user: User):
        """admin 发帖直接 status=1，不触发后台任务"""
        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        r = await client.post(
            "/api/v1/posts",
            json={"post_type": "general", "content": "管理员帖"},
            headers=auth_header(token),
        )
        assert r.status_code == 200
        assert r.json()["data"]["status"] == 1

    @pytest.mark.asyncio
    async def test_student_post_has_pending_status(self, client: AsyncClient, student_user: User):
        """student 发帖初始状态为 0（待审核），后台任务会被调度"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.post(
            "/api/v1/posts",
            json={"post_type": "general", "content": "测试帖", "images": ["/static/posts/2026/1.jpg"]},
            headers=auth_header(token),
        )
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["status"] == 0  # 待审核
        assert "审核中" in r.json()["message"]
