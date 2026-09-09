"""访问控制补漏测试：封禁/待审帖可见性、封禁帖互动、图片域限制（SSRF）、参数边界。

背景：列表接口过滤 status==1，但详情/互动/评论列表此前只查存在性——
按序号 ID 枚举即可读到被封禁内容并与之互动，旁路整个审核系统。
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.post import Post
from app.models.user import User
from app.utils.security import create_access_token
from tests.conftest import TestSession, auth_header


def _token(user: User) -> str:
    return create_access_token({"sub": str(user.id), "role": user.role})


async def _seed_post(user_id, content="测试帖", status=1) -> int:
    async with TestSession() as db:
        p = Post(user_id=user_id, post_type="general", content=content, images=[], status=status)
        db.add(p)
        await db.commit()
        await db.refresh(p)
        return p.id


class TestHiddenPostVisibility:
    """非 status==1 的帖子：陌生人 404；作者与 admin 可见（自查待审/被封帖）。"""

    async def test_banned_post_hidden_from_stranger(self, client, student_user, admin_user):
        pid = await _seed_post(student_user.id, status=-1)
        r = await client.get(f"/api/v1/posts/{pid}", headers=auth_header(_token(admin_user)))
        # 先用另一个学生当"陌生人"
        async with TestSession() as db:
            stranger = User(openid=f"stranger_{pid}", nickname="路人", role="student", is_verified=True)
            db.add(stranger)
            await db.commit()
            await db.refresh(stranger)
        r = await client.get(f"/api/v1/posts/{pid}", headers=auth_header(_token(stranger)))
        assert r.status_code == 404
        # 游客也 404
        r2 = await client.get(f"/api/v1/posts/{pid}")
        assert r2.status_code == 404

    async def test_banned_post_visible_to_author_and_admin(self, client, student_user, admin_user):
        pid = await _seed_post(student_user.id, status=-1)
        r_author = await client.get(f"/api/v1/posts/{pid}", headers=auth_header(_token(student_user)))
        assert r_author.status_code == 200
        assert r_author.json()["data"]["status"] == -1

        r_admin = await client.get(f"/api/v1/posts/{pid}", headers=auth_header(_token(admin_user)))
        assert r_admin.status_code == 200

    async def test_pending_post_hidden_from_stranger(self, client, student_user, admin_user):
        pid = await _seed_post(student_user.id, status=0)
        async with TestSession() as db:
            stranger = User(openid=f"stranger_p{pid}", nickname="路人2", role="student", is_verified=True)
            db.add(stranger)
            await db.commit()
            await db.refresh(stranger)
        r = await client.get(f"/api/v1/posts/{pid}", headers=auth_header(_token(stranger)))
        assert r.status_code == 404
        r_author = await client.get(f"/api/v1/posts/{pid}", headers=auth_header(_token(student_user)))
        assert r_author.status_code == 200


class TestHiddenPostInteraction:
    """封禁/待审帖不可被点赞/评论/收藏，评论列表不可读。"""

    async def _stranger(self, key):
        async with TestSession() as db:
            u = User(openid=key, nickname="陌生人", role="student", is_verified=True)
            db.add(u)
            await db.commit()
            await db.refresh(u)
            return u

    async def test_no_like_comment_favorite_on_banned(self, client, student_user):
        pid = await _seed_post(student_user.id, status=-1)
        stranger = await self._stranger(f"st_like_{pid}")
        headers = auth_header(_token(stranger))
        assert (await client.post(f"/api/v1/posts/{pid}/like", headers=headers)).status_code == 404
        assert (await client.post(f"/api/v1/posts/{pid}/comments", json={"content": "嗨"},
                                  headers=headers)).status_code == 404
        assert (await client.post(f"/api/v1/posts/{pid}/favorite", headers=headers)).status_code == 404
        assert (await client.get(f"/api/v1/posts/{pid}/comments", headers=headers)).status_code == 404


class TestImageDomainRestriction:
    """images 仅允许 /static/ 相对路径——SSRF 根因消除。"""

    async def test_external_url_rejected(self, client, student_user):
        for evil in ("http://169.254.169.254/latest/meta-data", "https://evil.com/a.jpg",
                     "//evil.com/a.jpg", "static/x.jpg"):
            r = await client.post(
                "/api/v1/posts",
                json={"post_type": "general", "content": "测试", "images": [evil]},
                headers=auth_header(_token(student_user)),
            )
            assert r.status_code == 422, evil

    async def test_static_path_accepted(self, client, student_user):
        r = await client.post(
            "/api/v1/posts",
            json={"post_type": "general", "content": "正常帖", "images": ["/static/posts/2026/a.jpg"]},
            headers=auth_header(_token(student_user)),
        )
        assert r.status_code == 200


class TestParamBounds:
    async def test_hot_ranking_limit_bounded(self, client):
        r = await client.get("/api/v1/user/hot-ranking", params={"limit": 9999999})
        assert r.status_code == 422
        r2 = await client.get("/api/v1/user/hot-ranking", params={"limit": 50})
        assert r2.status_code == 200

    async def test_non_uuid_user_route_422(self, client):
        """非 UUID user_id 走参数校验 422，而不是 500。"""
        r = await client.get("/api/v1/users/not-a-uuid/profile")
        assert r.status_code == 422
