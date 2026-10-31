from tests.production_helpers import approve_comments
"""互动模块测试：评论 / 点赞 / 收藏 / 足迹 / 个人统计 / 帖子计数。"""

import pytest
from httpx import AsyncClient

from app.models.user import User
from app.utils.security import create_access_token
from tests.conftest import TestSession, auth_header


# ---- 辅助 ----

async def _seed_post(user_id, post_type="general", content="测试帖子", status=1):
    from app.models.post import Post
    async with TestSession() as db:
        post = Post(user_id=user_id, post_type=post_type, content=content, status=status)
        db.add(post)
        await db.commit()
        await db.refresh(post)
        return post


def _token(user: User) -> str:
    return create_access_token({"sub": str(user.id), "role": user.role})


# ============================================================
# 点赞
# ============================================================


class TestLike:
    @pytest.mark.asyncio
    async def test_like_increments_count(self, client: AsyncClient, student_user: User, admin_user: User):
        post = await _seed_post(admin_user.id, status=1)
        r = await client.post(f"/api/v1/posts/{post.id}/like", headers=auth_header(_token(student_user)))
        assert r.status_code == 200
        assert r.json()["data"]["liked"] is True
        assert r.json()["data"]["like_count"] == 1

    @pytest.mark.asyncio
    async def test_like_is_idempotent(self, client: AsyncClient, student_user: User, admin_user: User):
        """重复点赞只 +1"""
        post = await _seed_post(admin_user.id, status=1)
        for _ in range(3):
            await client.post(f"/api/v1/posts/{post.id}/like", headers=auth_header(_token(student_user)))
        r = await client.get(f"/api/v1/posts/{post.id}", headers=auth_header(_token(student_user)))
        assert r.json()["data"]["like_count"] == 1
        assert r.json()["data"]["is_liked"] is True

    @pytest.mark.asyncio
    async def test_unlike_decrements(self, client: AsyncClient, student_user: User, admin_user: User):
        post = await _seed_post(admin_user.id, status=1)
        await client.post(f"/api/v1/posts/{post.id}/like", headers=auth_header(_token(student_user)))
        r = await client.delete(f"/api/v1/posts/{post.id}/like", headers=auth_header(_token(student_user)))
        assert r.status_code == 200
        assert r.json()["data"]["liked"] is False
        assert r.json()["data"]["like_count"] == 0

    @pytest.mark.asyncio
    async def test_unlike_not_below_zero(self, client: AsyncClient, student_user: User, admin_user: User):
        """取消未赞的帖子，计数保持 0"""
        post = await _seed_post(admin_user.id, status=1)
        r = await client.delete(f"/api/v1/posts/{post.id}/like", headers=auth_header(_token(student_user)))
        assert r.status_code == 200
        assert r.json()["data"]["like_count"] == 0

    @pytest.mark.asyncio
    async def test_guest_cannot_like(self, client: AsyncClient, guest_user: User, admin_user: User):
        post = await _seed_post(admin_user.id, status=1)
        r = await client.post(f"/api/v1/posts/{post.id}/like", headers=auth_header(_token(guest_user)))
        assert r.status_code == 403


# ============================================================
# 评论
# ============================================================


class TestComment:
    @pytest.mark.asyncio
    async def test_create_comment(self, client: AsyncClient, student_user: User, admin_user: User):
        post = await _seed_post(admin_user.id, status=1)
        r = await client.post(
            f"/api/v1/posts/{post.id}/comments",
            json={"content": "好帖"},
            headers=auth_header(_token(student_user)),
        )
        await approve_comments()
        assert r.status_code == 200
        assert r.json()["data"]["content"] == "好帖"
        assert r.json()["data"]["status"] == 0
        assert r.json()["data"]["comment_count"] == 0

    @pytest.mark.asyncio
    async def test_list_comments(self, client: AsyncClient, student_user: User, admin_user: User):
        post = await _seed_post(admin_user.id, status=1)
        for i in range(3):
            await client.post(
                f"/api/v1/posts/{post.id}/comments",
                json={"content": f"c{i}"},
                headers=auth_header(_token(student_user)),
            )
            await approve_comments()
        r = await client.get(f"/api/v1/posts/{post.id}/comments")
        assert r.status_code == 200
        items = r.json()["data"]["items"]
        assert len(items) == 3

    @pytest.mark.asyncio
    async def test_delete_own_comment(self, client: AsyncClient, student_user: User, admin_user: User):
        post = await _seed_post(admin_user.id, status=1)
        r = await client.post(
            f"/api/v1/posts/{post.id}/comments",
            json={"content": "删我"},
            headers=auth_header(_token(student_user)),
        )
        await approve_comments()
        cid = r.json()["data"]["id"]
        r2 = await client.delete(f"/api/v1/comments/{cid}", headers=auth_header(_token(student_user)))
        assert r2.status_code == 200
        # 计数随之减少
        r3 = await client.get(f"/api/v1/posts/{post.id}")
        assert r3.json()["data"]["comment_count"] == 0

    @pytest.mark.asyncio
    async def test_cannot_delete_others_comment(self, client: AsyncClient, student_user: User, admin_user: User):
        """删除他人评论 -> 403"""
        post = await _seed_post(admin_user.id, status=1)
        r = await client.post(
            f"/api/v1/posts/{post.id}/comments",
            json={"content": "管理员的评论"},
            headers=auth_header(_token(admin_user)),
        )
        await approve_comments()
        cid = r.json()["data"]["id"]
        r2 = await client.delete(f"/api/v1/comments/{cid}", headers=auth_header(_token(student_user)))
        assert r2.status_code == 403

    @pytest.mark.asyncio
    async def test_guest_cannot_comment(self, client: AsyncClient, guest_user: User, admin_user: User):
        post = await _seed_post(admin_user.id, status=1)
        r = await client.post(
            f"/api/v1/posts/{post.id}/comments",
            json={"content": "x"},
            headers=auth_header(_token(guest_user)),
        )
        await approve_comments()
        assert r.status_code == 403


# ============================================================
# 收藏
# ============================================================


class TestFavorite:
    @pytest.mark.asyncio
    async def test_favorite_and_list(self, client: AsyncClient, student_user: User, admin_user: User):
        post = await _seed_post(admin_user.id, status=1)
        r = await client.post(f"/api/v1/posts/{post.id}/favorite", headers=auth_header(_token(student_user)))
        assert r.status_code == 200
        assert r.json()["data"]["favorited"] is True

        r2 = await client.get("/api/v1/me/favorites", headers=auth_header(_token(student_user)))
        assert r2.status_code == 200
        assert len(r2.json()["data"]["items"]) == 1

    @pytest.mark.asyncio
    async def test_favorite_idempotent(self, client: AsyncClient, student_user: User, admin_user: User):
        post = await _seed_post(admin_user.id, status=1)
        for _ in range(3):
            await client.post(f"/api/v1/posts/{post.id}/favorite", headers=auth_header(_token(student_user)))
        r = await client.get("/api/v1/me/favorites", headers=auth_header(_token(student_user)))
        assert len(r.json()["data"]["items"]) == 1

    @pytest.mark.asyncio
    async def test_unfavorite(self, client: AsyncClient, student_user: User, admin_user: User):
        post = await _seed_post(admin_user.id, status=1)
        await client.post(f"/api/v1/posts/{post.id}/favorite", headers=auth_header(_token(student_user)))
        r = await client.delete(f"/api/v1/posts/{post.id}/favorite", headers=auth_header(_token(student_user)))
        assert r.status_code == 200
        assert r.json()["data"]["favorited"] is False
        r2 = await client.get("/api/v1/me/favorites", headers=auth_header(_token(student_user)))
        assert len(r2.json()["data"]["items"]) == 0


# ============================================================
# 足迹 + 浏览计数
# ============================================================


class TestFootprint:
    @pytest.mark.asyncio
    async def test_detail_records_footprint_and_view(self, client: AsyncClient, student_user: User, admin_user: User):
        """认证用户看详情：记足迹 + view_count+1"""
        post = await _seed_post(admin_user.id, status=1)
        await client.get(f"/api/v1/posts/{post.id}", headers=auth_header(_token(student_user)))
        r = await client.get("/api/v1/me/footprints", headers=auth_header(_token(student_user)))
        assert r.status_code == 200
        items = r.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["id"] == post.id

        # view_count 至少 1
        r2 = await client.get(f"/api/v1/posts/{post.id}", headers=auth_header(_token(student_user)))
        assert r2.json()["data"]["view_count"] >= 1

    @pytest.mark.asyncio
    async def test_guest_detail_no_footprint(self, client: AsyncClient, admin_user: User):
        """游客看详情不记足迹"""
        post = await _seed_post(admin_user.id, status=1)
        await client.get(f"/api/v1/posts/{post.id}")
        # 无 token 访问 /me/footprints -> 403（HTTPBearer 默认）
        r = await client.get("/api/v1/me/footprints")
        assert r.status_code == 401


# ============================================================
# 个人统计
# ============================================================


class TestStats:
    @pytest.mark.asyncio
    async def test_stats_counts(self, client: AsyncClient, student_user: User, admin_user: User):
        # student 发 2 帖 + 1 评论 + 收藏 1
        p1 = await _seed_post(student_user.id, content="我的帖1", status=1)
        await _seed_post(student_user.id, content="我的帖2", status=1)
        post = await _seed_post(admin_user.id, status=1)
        await client.post(f"/api/v1/posts/{post.id}/comments", json={"content": "hi"},
                          headers=auth_header(_token(student_user)))
        await approve_comments()
        await client.post(f"/api/v1/posts/{post.id}/favorite", headers=auth_header(_token(student_user)))

        r = await client.get("/api/v1/me/stats", headers=auth_header(_token(student_user)))
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["posts_count"] == 2
        assert data["comments_count"] == 1
        assert data["favorites_count"] == 1

    @pytest.mark.asyncio
    async def test_stats_requires_auth(self, client: AsyncClient):
        r = await client.get("/api/v1/me/stats")
        assert r.status_code == 401


# ============================================================
# 帖子列表/详情带互动字段
# ============================================================


class TestPostInteractionFields:
    @pytest.mark.asyncio
    async def test_list_has_count_fields(self, client: AsyncClient, student_user: User):
        await _seed_post(student_user.id, status=1)
        r = await client.get("/api/v1/posts")
        item = r.json()["data"]["items"][0]
        for k in ("like_count", "comment_count", "view_count"):
            assert k in item

    @pytest.mark.asyncio
    async def test_detail_has_user_view_fields(self, client: AsyncClient, student_user: User, admin_user: User):
        post = await _seed_post(admin_user.id, status=1)
        await client.post(f"/api/v1/posts/{post.id}/like", headers=auth_header(_token(student_user)))
        r = await client.get(f"/api/v1/posts/{post.id}", headers=auth_header(_token(student_user)))
        data = r.json()["data"]
        assert data["is_liked"] is True
        assert data["is_favorited"] is False
