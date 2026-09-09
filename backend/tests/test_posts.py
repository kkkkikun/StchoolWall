"""Posts 模块测试：发帖、列表、详情（隐私隔离）、状态变更、举报"""

import pytest
from httpx import AsyncClient

from app.models.user import User
from app.utils.security import create_access_token
from tests.conftest import TestSession, auth_header

import uuid


# ---- 辅助：创建帖子 ----

async def _seed_post(user_id, post_type="general", content="测试帖子", status=1):
    from app.models.post import Post
    async with TestSession() as db:
        post = Post(user_id=user_id, post_type=post_type, content=content, status=status)
        db.add(post)
        await db.commit()
        await db.refresh(post)
        return post


# ============================================================
# POST /api/v1/posts — 发布帖子
# ============================================================


class TestCreatePost:

    @pytest.mark.asyncio
    async def test_student_create_post(self, client: AsyncClient, student_user: User):
        """student 发帖成功，初始状态为 0（待审核）"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.post("/api/v1/posts", json={
            "post_type": "general",
            "content": "万能墙测试帖",
        }, headers=auth_header(token))
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["status"] == 0

    @pytest.mark.asyncio
    async def test_admin_create_post_auto_approved(self, client: AsyncClient, admin_user: User):
        """admin 发帖直接通过审核，状态为 1"""
        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        r = await client.post("/api/v1/posts", json={
            "post_type": "general",
            "content": "管理员帖子",
        }, headers=auth_header(token))
        assert r.status_code == 200
        assert r.json()["data"]["status"] == 1

    @pytest.mark.asyncio
    async def test_admin_create_advertisement(self, client: AsyncClient, admin_user: User):
        """admin 可以发 advertisement 类型"""
        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        r = await client.post("/api/v1/posts", json={
            "post_type": "advertisement",
            "content": "[商家] 新开剧本杀",
        }, headers=auth_header(token))
        assert r.status_code == 200
        assert r.json()["data"]["status"] == 1

    @pytest.mark.asyncio
    async def test_student_cannot_create_advertisement(self, client: AsyncClient, student_user: User):
        """student 不能发 advertisement"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.post("/api/v1/posts", json={
            "post_type": "advertisement",
            "content": "偷发广告",
        }, headers=auth_header(token))
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_create_post_with_all_fields(self, client: AsyncClient, student_user: User):
        """带图片、价格、标签的发帖"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.post("/api/v1/posts", json={
            "post_type": "second_hand",
            "content": "出算法导论",
            "images": ["/static/posts/2026/1.jpg"],
            "price": 25.0,
        }, headers=auth_header(token))
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_guest_cannot_create_post(self, client: AsyncClient, guest_user: User):
        """guest 不能发帖"""
        token = create_access_token({"sub": str(guest_user.id), "role": "guest"})
        r = await client.post("/api/v1/posts", json={
            "post_type": "general",
            "content": "试试",
        }, headers=auth_header(token))
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_no_token_cannot_create(self, client: AsyncClient):
        """无 Token 不能发帖"""
        r = await client.post("/api/v1/posts", json={
            "post_type": "general", "content": "test",
        })
        assert r.status_code == 403


# ============================================================
# GET /api/v1/posts — 帖子列表
# ============================================================


class TestListPosts:

    @pytest.mark.asyncio
    async def test_empty_list(self, client: AsyncClient):
        """无帖子时返回空列表"""
        r = await client.get("/api/v1/posts")
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["items"] == []
        assert body["data"]["has_more"] is False

    @pytest.mark.asyncio
    async def test_list_returns_visible_posts(self, client: AsyncClient, student_user: User):
        """只返回 status=1 的非广告帖子 + 广告"""
        await _seed_post(student_user.id, content="可见帖子", status=1)
        await _seed_post(student_user.id, content="待审核", status=0)
        await _seed_post(student_user.id, content="已删除", status=-2)
        r = await client.get("/api/v1/posts")
        items = r.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["content"] == "可见帖子"

    @pytest.mark.asyncio
    async def test_advertisements_not_in_feed(self, client: AsyncClient, admin_user: User, student_user: User):
        """广告帖不再混入 feed（轮播位由独立 Banner 表承接）"""
        await _seed_post(student_user.id, content="普通帖", status=1)
        await _seed_post(admin_user.id, post_type="advertisement", content="广告帖", status=1)
        r = await client.get("/api/v1/posts")
        items = r.json()["data"]["items"]
        assert [it["content"] for it in items] == ["普通帖"]

    @pytest.mark.asyncio
    async def test_list_public_no_token(self, client: AsyncClient, student_user: User):
        """列表接口无需 Token"""
        await _seed_post(student_user.id, content="公开", status=1)
        r = await client.get("/api/v1/posts")
        assert r.status_code == 200
        assert len(r.json()["data"]["items"]) == 1

    @pytest.mark.asyncio
    async def test_list_does_not_expose_real_name(self, client: AsyncClient, student_user: User):
        """列表不暴露 real_name"""
        await _seed_post(student_user.id, status=1)
        r = await client.get("/api/v1/posts")
        item = r.json()["data"]["items"][0]
        assert "real_name" not in item["user"]


# ============================================================
# GET /api/v1/posts/{post_id} — 帖子详情（隐私隔离）
# ============================================================


class TestPostDetail:

    @pytest.mark.asyncio
    async def test_admin_sees_everything(self, client: AsyncClient, admin_user: User, student_user: User):
        """admin 可看 real_name、student_id、wechat_id"""
        post = await _seed_post(student_user.id, status=1)
        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        r = await client.get(f"/api/v1/posts/{post.id}", headers=auth_header(token))
        data = r.json()["data"]
        assert data["user"]["real_name"] == student_user.real_name
        assert data["user"]["student_id"] == student_user.student_id
        assert data["contact_wechat"] == student_user.wechat_id

    @pytest.mark.asyncio
    async def test_author_sees_own_real_name(self, client: AsyncClient, student_user: User):
        """作者查看自己的帖子，能看到 real_name"""
        post = await _seed_post(student_user.id, status=1)
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.get(f"/api/v1/posts/{post.id}", headers=auth_header(token))
        data = r.json()["data"]
        assert data["user"].get("real_name") == student_user.real_name

    @pytest.mark.asyncio
    async def test_student_sees_wechat_but_not_real_name(self, client: AsyncClient, student_user: User, admin_user: User):
        """其他 student 查看：能看到 wechat_id，看不到 real_name"""
        post = await _seed_post(admin_user.id, status=1)
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.get(f"/api/v1/posts/{post.id}", headers=auth_header(token))
        data = r.json()["data"]
        assert data.get("contact_wechat") == admin_user.wechat_id
        assert "real_name" not in data["user"]

    @pytest.mark.asyncio
    async def test_guest_sees_nothing_sensitive(self, client: AsyncClient, student_user: User):
        """guest 查看：无 contact_wechat，无 real_name"""
        post = await _seed_post(student_user.id, status=1)
        r = await client.get(f"/api/v1/posts/{post.id}")
        data = r.json()["data"]
        assert data.get("contact_wechat") is None
        assert "real_name" not in data["user"]

    @pytest.mark.asyncio
    async def test_nonexistent_post(self, client: AsyncClient):
        """不存在的帖子返回 404"""
        r = await client.get("/api/v1/posts/99999")
        assert r.status_code == 404


# ============================================================
# PUT /api/v1/posts/{post_id}/status — 状态变更
# ============================================================


class TestUpdateStatus:

    @pytest.mark.asyncio
    async def test_author_archive_post(self, client: AsyncClient, student_user: User):
        """作者标记已解决 -> status=2"""
        post = await _seed_post(student_user.id, status=1)
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.put(f"/api/v1/posts/{post.id}/status?status=2", headers=auth_header(token))
        assert r.status_code == 200
        assert r.json()["data"]["status"] == 2

    @pytest.mark.asyncio
    async def test_author_soft_delete(self, client: AsyncClient, student_user: User):
        """作者软删除 -> status=-2"""
        post = await _seed_post(student_user.id, status=1)
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.put(f"/api/v1/posts/{post.id}/status?status=-2", headers=auth_header(token))
        assert r.status_code == 200
        assert r.json()["data"]["status"] == -2

    @pytest.mark.asyncio
    async def test_admin_block_post(self, client: AsyncClient, student_user: User, admin_user: User):
        """admin 封禁帖子 -> status=-1"""
        post = await _seed_post(student_user.id, status=1)
        token = create_access_token({"sub": str(admin_user.id), "role": "admin"})
        r = await client.put(f"/api/v1/posts/{post.id}/status?status=-1", headers=auth_header(token))
        assert r.status_code == 200
        assert r.json()["data"]["status"] == -1

    @pytest.mark.asyncio
    async def test_cannot_archive_others_post(self, client: AsyncClient, student_user: User, admin_user: User):
        """不能归档别人的帖子"""
        post = await _seed_post(admin_user.id, status=1)
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.put(f"/api/v1/posts/{post.id}/status?status=2", headers=auth_header(token))
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_invalid_transition(self, client: AsyncClient, student_user: User):
        """无效的状态流转被拒绝（从 0 直接到 2）"""
        post = await _seed_post(student_user.id, status=0)
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.put(f"/api/v1/posts/{post.id}/status?status=2", headers=auth_header(token))
        assert r.status_code == 400


# ============================================================
# POST /api/v1/posts/{post_id}/report — 举报
# ============================================================


class TestReportPost:

    @pytest.mark.asyncio
    async def test_report_success(self, client: AsyncClient, student_user: User, admin_user: User):
        """举报成功，帖子状态不受影响"""
        post = await _seed_post(admin_user.id, status=1)
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.post(f"/api/v1/posts/{post.id}/report", json={
            "reason": "虚假信息",
            "description": "测试举报",
        }, headers=auth_header(token))
        assert r.status_code == 200
        assert "举报成功" in r.json()["message"]

        # 帖子状态不变
        r2 = await client.get(f"/api/v1/posts/{post.id}", headers=auth_header(token))
        assert r2.json()["data"]["status"] == 1

    @pytest.mark.asyncio
    async def test_report_nonexistent_post(self, client: AsyncClient, student_user: User):
        """举报不存在的帖子 -> 404"""
        token = create_access_token({"sub": str(student_user.id), "role": "student"})
        r = await client.post("/api/v1/posts/99999/report", json={
            "reason": "不存在",
        }, headers=auth_header(token))
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_guest_cannot_report(self, client: AsyncClient, guest_user: User, student_user: User):
        """guest 不能举报"""
        post = await _seed_post(student_user.id, status=1)
        token = create_access_token({"sub": str(guest_user.id), "role": "guest"})
        r = await client.post(f"/api/v1/posts/{post.id}/report", json={
            "reason": "试试",
        }, headers=auth_header(token))
        assert r.status_code == 403
