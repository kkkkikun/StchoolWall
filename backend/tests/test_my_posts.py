"""GET /posts/my 测试：我的帖子（含各状态，按 status 筛选）。"""
import pytest
from httpx import AsyncClient

from app.models.post import Post
from app.models.user import User
from tests.conftest import TestSession, auth_header

pytestmark = pytest.mark.asyncio


async def _seed(user_id, content, status=1) -> int:
    async with TestSession() as db:
        p = Post(user_id=user_id, post_type="general", content=content, status=status)
        db.add(p)
        await db.commit()
        await db.refresh(p)
        return p.id


class TestMyPosts:
    async def test_returns_own_all_statuses(self, client: AsyncClient, student_user: User, admin_user: User):
        """返回自己的全部状态帖子（含待审/封禁），不含他人帖子。"""
        await _seed(student_user.id, "我的正常", 1)
        await _seed(student_user.id, "我的待审", 0)
        await _seed(student_user.id, "我的封禁", -1)
        await _seed(admin_user.id, "别人的", 1)

        token = auth_header("x")  # 占位，下面用真实 token
        from app.utils.security import create_access_token
        headers = {"Authorization": f"Bearer {create_access_token({'sub': str(student_user.id), 'role': 'student'})}"}

        resp = await client.get("/api/v1/posts/my", headers=headers)
        assert resp.status_code == 200
        contents = [it["content"] for it in resp.json()["data"]["items"]]
        assert set(contents) == {"我的正常", "我的待审", "我的封禁"}

    async def test_status_filter(self, client: AsyncClient, student_user: User):
        """?status=0 只返回待审。"""
        await _seed(student_user.id, "待审的", 0)
        await _seed(student_user.id, "正常的", 1)

        from app.utils.security import create_access_token
        headers = {"Authorization": f"Bearer {create_access_token({'sub': str(student_user.id), 'role': 'student'})}"}

        resp = await client.get("/api/v1/posts/my?status=0", headers=headers)
        contents = [it["content"] for it in resp.json()["data"]["items"]]
        assert contents == ["待审的"]

    async def test_requires_login(self, client: AsyncClient):
        resp = await client.get("/api/v1/posts/my")
        assert resp.status_code == 401
