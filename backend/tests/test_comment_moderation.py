from tests.production_helpers import approve_comments
"""评论头像透出 + 评论本地审核（同步词检：hard 拒 / gray 待审 / clean 即见）。"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.moderation_record import ModerationRecord
from app.models.notification import Notification
from app.models.post import Post
from app.models.sensitive_word import SensitiveWord
from app.models.user import User
from app.utils.security import create_access_token
from tests.conftest import TestSession, auth_header


def _token(user: User) -> str:
    return create_access_token({"sub": str(user.id), "role": user.role})


async def _seed_word(word: str, level: str = "hard") -> None:
    async with TestSession() as db:
        db.add(SensitiveWord(word=word, level=level))
        await db.commit()


async def _seed_post(user_id, content="评论区测试帖") -> int:
    async with TestSession() as db:
        p = Post(user_id=user_id, post_type="general", content=content, images=[], status=1)
        db.add(p)
        await db.commit()
        await db.refresh(p)
        return p.id


async def _set_avatar(user: User, url: str):
    async with TestSession() as db:
        u = await db.get(User, user.id)
        u.avatar_url = url
        await db.commit()


class TestCommentAvatar:

    @pytest.mark.asyncio
    async def test_comment_list_includes_avatar(self, client, admin_user, student_user):
        await _set_avatar(student_user, "/static/avatars/2026/cmt.jpg")
        pid = await _seed_post(admin_user.id)
        await client.post(
            f"/api/v1/posts/{pid}/comments",
            json={"content": "头像测试评论"},
            headers=auth_header(_token(student_user)),
        )
        await approve_comments()
        r = await client.get(f"/api/v1/posts/{pid}/comments")
        items = r.json()["data"]["items"]
        assert items[0]["user"]["avatar_url"] == "/static/avatars/2026/cmt.jpg"


class TestCommentModeration:

    @pytest.mark.asyncio
    async def test_hard_word_rejected(self, client, admin_user, student_user):
        """硬词评论：400 拒绝，不落库，审核记录 reject。"""
        await _seed_word("代考", "hard")
        pid = await _seed_post(admin_user.id)
        r = await client.post(
            f"/api/v1/posts/{pid}/comments",
            json={"content": "有人代考吗"},
            headers=auth_header(_token(student_user)),
        )
        assert r.status_code == 400
        from app.models.interaction import Comment
        async with TestSession() as db:
            n = (await db.execute(select(Comment).where(Comment.post_id == pid))).scalars().all()
            assert n == []
        async with TestSession() as db:
            rec = (await db.execute(
                select(ModerationRecord).where(ModerationRecord.comment_id.is_(None),
                                               ModerationRecord.source == "rule")
            )).scalars().first()
        # 拒绝记录挂在被评帖上（comment 未创建，用 post_id 关联 + detail 说明）
        assert rec is not None and rec.verdict == "reject"

    @pytest.mark.asyncio
    async def test_gray_word_pending_then_approve(self, client, console_headers, admin_user, student_user):
        """灰词评论：落库 status=0 公开不可见 → 管理台过审 → 可见 + 计数 + 通知帖子作者。"""
        await _seed_word("垃圾人", "gray")
        pid = await _seed_post(admin_user.id)
        r = await client.post(
            f"/api/v1/posts/{pid}/comments",
            json={"content": "你真是个垃圾人"},
            headers=auth_header(_token(student_user)),
        )
        assert r.status_code == 200
        assert r.json()["data"]["status"] == 0

        # 公开列表不可见、不计数
        pub = await client.get(f"/api/v1/posts/{pid}/comments")
        assert pub.json()["data"]["items"] == []

        # 管理台待审队列可见
        pending = await client.get("/api/v1/admin/comments", params={"status": 0}, headers=console_headers)
        assert any(c["content"] == "你真是个垃圾人" for c in pending.json()["data"]["items"])

        # 过审
        cid = r.json()["data"]["id"]
        approve = await client.put(f"/api/v1/admin/comments/{cid}/status", params={"status": 1},
                                   headers=console_headers)
        assert approve.status_code == 200

        pub2 = await client.get(f"/api/v1/posts/{pid}/comments")
        assert any(c["content"] == "你真是个垃圾人" for c in pub2.json()["data"]["items"])

        # 计数 + 通知帖子作者
        detail = await client.get(f"/api/v1/posts/{pid}")
        assert detail.json()["data"]["comment_count"] == 1
        async with TestSession() as db:
            notif = (await db.execute(
                select(Notification).where(Notification.type == "comment", Notification.post_id == pid)
            )).scalars().first()
            assert notif is not None

    @pytest.mark.asyncio
    async def test_clean_comment_waits_for_machine_review(self, client, admin_user, student_user):
        """干净评论同样先待审，机器通过后才公开。"""
        pid = await _seed_post(admin_user.id)
        r = await client.post(
            f"/api/v1/posts/{pid}/comments",
            json={"content": "正常的评论"},
            headers=auth_header(_token(student_user)),
        )
        assert r.status_code == 200
        assert r.json()["data"]["status"] == 0
        pending = await client.get(f"/api/v1/posts/{pid}/comments")
        assert pending.json()["data"]["items"] == []
        await approve_comments()
        pub = await client.get(f"/api/v1/posts/{pid}/comments")
        assert len(pub.json()["data"]["items"]) == 1

    @pytest.mark.asyncio
    async def test_admin_reject_pending_comment(self, client, console_headers, admin_user, student_user):
        """管理台拒审待审评论 → 永不可见。"""
        await _seed_word("垃圾人", "gray")
        pid = await _seed_post(admin_user.id)
        r = await client.post(
            f"/api/v1/posts/{pid}/comments",
            json={"content": "又一条垃圾人评论"},
            headers=auth_header(_token(student_user)),
        )
        cid = r.json()["data"]["id"]
        reject = await client.put(f"/api/v1/admin/comments/{cid}/status", params={"status": -1},
                                  headers=console_headers)
        assert reject.status_code == 200
        pub = await client.get(f"/api/v1/posts/{pid}/comments")
        assert pub.json()["data"]["items"] == []
