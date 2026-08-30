"""Banner（首页轮播广告位）测试：公开列表投放窗口过滤 + admin CRUD + 权限。"""
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.banner import Banner
from app.models.user import User
from tests.conftest import TestSession, auth_header

pytestmark = pytest.mark.asyncio


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _seed_banner(**kwargs) -> Banner:
    defaults = dict(title="测试广告", sort=0, status=1)
    defaults.update(kwargs)
    async with TestSession() as db:
        b = Banner(**defaults)
        db.add(b)
        await db.commit()
        await db.refresh(b)
        return b


class TestPublicBanners:
    async def test_only_active_and_in_window(self, client: AsyncClient):
        """公开接口只返回 status=1 且投放期内的 banner，按 sort 降序。"""
        now = _utcnow()
        await _seed_banner(title="投放中-权重高", sort=10)
        await _seed_banner(title="投放中-权重低", sort=1)
        await _seed_banner(title="已下架", status=0, sort=99)
        await _seed_banner(title="未开始", start_at=now + timedelta(hours=1), sort=99)
        await _seed_banner(title="已结束", end_at=now - timedelta(hours=1), sort=99)

        resp = await client.get("/api/v1/banners")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        titles = [it["title"] for it in items]
        assert titles == ["投放中-权重高", "投放中-权重低"]

    async def test_boundary_inclusive(self, client: AsyncClient):
        """start_at<=now<=end_at 边界值应包含。"""
        now = _utcnow()
        await _seed_banner(title="边界", start_at=now - timedelta(seconds=1), end_at=now + timedelta(seconds=1))

        resp = await client.get("/api/v1/banners")
        items = resp.json()["data"]["items"]
        assert [it["title"] for it in items] == ["边界"]

    async def test_no_auth_required(self, client: AsyncClient):
        """无 token 可访问，响应不含管理字段。"""
        await _seed_banner(title="公开", tag="活动", desc="副标题", image_url="http://x/y.png")
        resp = await client.get("/api/v1/banners")
        assert resp.status_code == 200
        item = resp.json()["data"]["items"][0]
        assert item["title"] == "公开"
        assert item["tag"] == "活动"
        # 不暴露任何创建者/管理信息
        assert "created_by" not in item
        assert "sort" not in item and "status" not in item


class TestBannerAdminCrud:
    async def test_student_forbidden(self, client: AsyncClient, student_token: str):
        for method, url in [
            ("get", "/api/v1/admin/banners"),
            ("post", "/api/v1/admin/banners"),
            ("put", "/api/v1/admin/banners/1"),
            ("delete", "/api/v1/admin/banners/1"),
        ]:
            resp = await getattr(client, method)(url, headers=auth_header(student_token))
            assert resp.status_code == 403, f"{method} {url} 应 403"

    async def test_anonymous_forbidden(self, client: AsyncClient):
        resp = await client.get("/api/v1/admin/banners")
        assert resp.status_code == 403

    async def test_full_crud_lifecycle(self, client: AsyncClient, admin_token: str, admin_user: User):
        from app.models.post import Post

        # 先建一个真实帖子做跳转目标（banners.post_id 有外键）
        async with TestSession() as db:
            post = Post(user_id=admin_user.id, post_type="general", content="目标帖", status=1)
            db.add(post)
            await db.commit()
            await db.refresh(post)
            target_post_id = post.id

        headers = auth_header(admin_token)

        # 创建（跳转到帖子）
        resp = await client.post("/api/v1/admin/banners", headers=headers, json={
            "title": "毕业季活动", "desc": "赢毕业礼包", "tag": "活动",
            "post_id": target_post_id, "sort": 5,
        })
        assert resp.status_code == 200, resp.text
        banner_id = resp.json()["data"]["id"]

        # 公开列表可见
        pub = await client.get("/api/v1/banners")
        assert [it["id"] for it in pub.json()["data"]["items"]] == [banner_id]

        # 更新：换外链 + 加投放窗口
        later = _utcnow() + timedelta(days=7)
        resp = await client.put(f"/api/v1/admin/banners/{banner_id}", headers=headers, json={
            "title": "毕业季·改", "link_url": "https://example.com/act", "end_at": later.isoformat(),
        })
        assert resp.status_code == 200
        item = resp.json()["data"]
        assert item["title"] == "毕业季·改"
        assert item["link_url"] == "https://example.com/act"
        assert item["post_id"] is None  # link_url 覆盖后 post_id 应被清空

        # admin 列表含下架的
        resp = await client.put(f"/api/v1/admin/banners/{banner_id}", headers=headers, json={"status": 0})
        assert resp.status_code == 200
        resp = await client.get("/api/v1/admin/banners", headers=headers)
        assert [it["id"] for it in resp.json()["data"]["items"]] == [banner_id]
        # 下架后公开不可见
        pub = await client.get("/api/v1/banners")
        assert pub.json()["data"]["items"] == []

        # 删除
        resp = await client.delete(f"/api/v1/admin/banners/{banner_id}", headers=headers)
        assert resp.status_code == 200
        resp = await client.get("/api/v1/admin/banners", headers=headers)
        assert resp.json()["data"]["items"] == []

    async def test_link_and_post_mutually_exclusive(self, client: AsyncClient, admin_token: str):
        """link_url 与 post_id 同时传 → 422。"""
        resp = await client.post("/api/v1/admin/banners", headers=auth_header(admin_token), json={
            "title": "冲突", "link_url": "https://a.com", "post_id": 1,
        })
        assert resp.status_code == 422

    async def test_bad_link_format_rejected(self, client: AsyncClient, admin_token: str):
        resp = await client.post("/api/v1/admin/banners", headers=auth_header(admin_token), json={
            "title": "坏链接", "link_url": "ftp://not-http",
        })
        assert resp.status_code == 422

    async def test_update_404(self, client: AsyncClient, admin_token: str):
        resp = await client.put("/api/v1/admin/banners/99999", headers=auth_header(admin_token), json={"title": "x"})
        assert resp.status_code == 404


class TestFeedAdCleanup:
    async def test_advertisement_posts_not_in_feed(self, client: AsyncClient, student_user: User, admin_user: User):
        """广告帖不再混入 feed（由 Banner 表接管轮播位）。"""
        from app.models.post import Post

        async with TestSession() as db:
            for i, ptype in enumerate(["general", "general", "advertisement"]):
                db.add(Post(
                    user_id=(student_user if ptype == "general" else admin_user).id,
                    post_type=ptype, content=f"帖子{i}", status=1,
                ))
            await db.commit()

        resp = await client.get("/api/v1/posts")
        items = resp.json()["data"]["items"]
        assert len(items) == 2
        assert all(it["post_type"] != "advertisement" for it in items)

    async def test_pagination_no_duplicate(self, client: AsyncClient, student_user: User):
        """翻页不重复：广告逻辑移除后两页 items 无重复 id。"""
        from app.models.post import Post

        async with TestSession() as db:
            for i in range(25):
                db.add(Post(user_id=student_user.id, post_type="general", content=f"帖子{i}", status=1))
            await db.commit()

        seen = set()
        cursor = None
        for _ in range(3):
            url = "/api/v1/posts" + (f"?cursor={cursor}" if cursor else "")
            data = (await client.get(url)).json()["data"]
            for it in data["items"]:
                assert it["id"] not in seen, "翻页出现重复帖子"
                seen.add(it["id"])
            if not data["has_more"]:
                break
            cursor = data["next_cursor"]
        assert len(seen) == 25
