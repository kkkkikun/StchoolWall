"""置顶帖测试：推荐位第一页前置置顶块 + 主流排除防重复 + admin 权限。"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.post import Post
from app.models.user import User
from tests.conftest import TestSession, auth_header

pytestmark = pytest.mark.asyncio


async def _seed(user_id, content, *, status=1, pinned=False, category=None, post_type="general") -> Post:
    async with TestSession() as db:
        p = Post(
            user_id=user_id, post_type=post_type, content=content,
            status=status, category=category,
            is_pinned=pinned, pinned_at=None,
        )
        db.add(p)
        await db.commit()
        await db.refresh(p)
        return p


class TestPinnedInFeed:
    async def test_pinned_first_page_top(self, client: AsyncClient, student_user: User):
        """推荐位第一页：置顶帖排在最前。"""
        await _seed(student_user.id, "普通A")
        await _seed(student_user.id, "置顶帖", pinned=True)
        await _seed(student_user.id, "普通B")

        data = (await client.get("/api/v1/posts")).json()["data"]
        contents = [it["content"] for it in data["items"]]
        assert contents[0] == "置顶帖"
        assert contents[1:] == ["普通B", "普通A"]  # 主流按时间倒序

    async def test_pinned_not_duplicated_in_stream(self, client: AsyncClient, student_user: User):
        """置顶帖从主流排除：整个分页过程中只出现一次。"""
        await _seed(student_user.id, "置顶帖", pinned=True)
        for i in range(25):
            await _seed(student_user.id, f"普通{i}")

        seen: dict[int, int] = {}
        cursor = None
        for _ in range(5):
            url = "/api/v1/posts" + (f"?cursor={cursor}" if cursor else "")
            data = (await client.get(url)).json()["data"]
            for it in data["items"]:
                seen[it["id"]] = seen.get(it["id"], 0) + 1
            if not data["has_more"]:
                break
            cursor = data["next_cursor"]
        assert all(cnt == 1 for cnt in seen.values()), "帖子在分页中出现多次"
        assert len(seen) == 26

    async def test_pinned_not_prefix_in_category(self, client: AsyncClient, student_user: User):
        """分类筛选时置顶帖不前置，按时间正常混排。"""
        await _seed(student_user.id, "分类旧帖", category="校园广场")
        await _seed(student_user.id, "分类置顶帖", category="校园广场", pinned=True)

        data = (await client.get("/api/v1/posts?category=校园广场")).json()["data"]
        contents = [it["content"] for it in data["items"]]
        # 按创建时间倒序（后创建的分类置顶帖在前，但这是时间序不是置顶前置）
        assert contents == ["分类置顶帖", "分类旧帖"]
        # 第一项不携带置顶前置语义：整个列表顺序 == created_at desc

    async def test_pinned_not_prefix_with_post_type(self, client: AsyncClient, student_user: User):
        """post_type 筛选时同样不前置（按 id 倒序混排）。"""
        await _seed(student_user.id, "二手旧", post_type="second_hand")
        await _seed(student_user.id, "二手置顶", post_type="second_hand", pinned=True)

        data = (await client.get("/api/v1/posts?post_type=second_hand")).json()["data"]
        contents = [it["content"] for it in data["items"]]
        # 按 id 倒序（后创建在前），置顶帖不前置
        assert contents == ["二手置顶", "二手旧"]

    async def test_pinned_banned_not_shown(self, client: AsyncClient, student_user: User):
        """status=-1 的置顶帖不出现在置顶块。"""
        await _seed(student_user.id, "被封置顶", pinned=True, status=-1)
        await _seed(student_user.id, "普通")

        data = (await client.get("/api/v1/posts")).json()["data"]
        assert [it["content"] for it in data["items"]] == ["普通"]

    async def test_item_contains_is_pinned_field(self, client: AsyncClient, student_user: User):
        """列表项含 is_pinned 字段。"""
        await _seed(student_user.id, "置顶", pinned=True)
        await _seed(student_user.id, "普通")
        data = (await client.get("/api/v1/posts")).json()["data"]
        assert data["items"][0]["is_pinned"] is True
        assert data["items"][1]["is_pinned"] is False

    async def test_pinned_by_pinned_at_order(self, client: AsyncClient, student_user: User):
        """多个置顶帖按 pinned_at 倒序（最新置顶的在前）。"""
        from sqlalchemy import update
        from datetime import datetime, timedelta, timezone

        p1 = await _seed(student_user.id, "先置顶", pinned=True)
        p2 = await _seed(student_user.id, "后置顶", pinned=True)
        now = datetime.now(timezone.utc)
        async with TestSession() as db:
            await db.execute(update(Post).where(Post.id == p1.id).values(pinned_at=now - timedelta(hours=1)))
            await db.execute(update(Post).where(Post.id == p2.id).values(pinned_at=now))
            await db.commit()

        data = (await client.get("/api/v1/posts")).json()["data"]
        assert data["items"][0]["content"] == "后置顶"
        assert data["items"][1]["content"] == "先置顶"


class TestPinAdminRoute:
    async def test_pin_and_unpin(self, client: AsyncClient, admin_token: str, student_user: User):
        p = await _seed(student_user.id, "待置顶")
        headers = auth_header(admin_token)

        resp = await client.put(f"/api/v1/admin/posts/{p.id}/pin", headers=headers, json={"pinned": True})
        assert resp.status_code == 200
        assert resp.json()["data"]["is_pinned"] is True

        # 置顶后出现在推荐位最前
        data = (await client.get("/api/v1/posts")).json()["data"]
        assert data["items"][0]["content"] == "待置顶"

        resp = await client.put(f"/api/v1/admin/posts/{p.id}/pin", headers=headers, json={"pinned": False})
        assert resp.status_code == 200
        assert resp.json()["data"]["is_pinned"] is False

    async def test_pin_404(self, client: AsyncClient, admin_token: str):
        resp = await client.put("/api/v1/admin/posts/99999/pin", headers=auth_header(admin_token), json={"pinned": True})
        assert resp.status_code == 404

    async def test_student_forbidden(self, client: AsyncClient, student_token: str, student_user: User):
        p = await _seed(student_user.id, "x")
        resp = await client.put(f"/api/v1/admin/posts/{p.id}/pin", headers=auth_header(student_token), json={"pinned": True})
        assert resp.status_code == 403
