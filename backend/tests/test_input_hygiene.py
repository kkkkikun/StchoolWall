"""批5 输入卫生测试：escape_like / CSV 公式注入 / body 上限 / wechat_id 帖型收敛 / verify 密码上限。"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.post import Post
from app.models.user import User
from app.utils.security import create_access_token
from tests.conftest import TestSession, auth_header


def _token(user: User) -> str:
    return create_access_token({"sub": str(user.id), "role": user.role})


async def _seed_post(user_id, post_type="general", status=1) -> int:
    async with TestSession() as db:
        p = Post(user_id=user_id, post_type=post_type, content="卫生测试帖", images=[], status=status)
        db.add(p)
        await db.commit()
        await db.refresh(p)
        return p.id


class TestEscapeLike:

    def test_wildcards_escaped(self):
        from app.utils.query import escape_like
        assert escape_like("100%_a\\b") == "100\\%\\_a\\\\b"
        assert escape_like("普通词") == "普通词"

    async def test_search_percent_treated_literally(self, client, student_user):
        """搜索 % 不再当通配符：无匹配内容时结果为空而不是全表命中。"""
        await _seed_post(student_user.id)
        r = await client.get("/api/v1/posts/search", params={"q": "%%%---"})
        assert r.status_code == 200
        assert r.json()["data"]["items"] == []


class TestCsvFormulaInjection:

    async def test_formula_cells_prefixed(self, client, console_headers, student_user):
        await _seed_post(student_user.id)
        async with TestSession() as db:
            p = Post(user_id=student_user.id, post_type="general",
                     content="=HYPERLINK(\"http://evil\",\"x\")", images=[], status=1)
            db.add(p)
            await db.commit()
        r = await client.get("/api/v1/admin/export/posts", headers=console_headers)
        body = r.content.decode("utf-8")
        # 单元格以 ' 前缀转义：CSV 中不得出现未转义的 ,"=HYP...（引号内紧跟=）
        assert ',"=HYPERLINK' not in body
        assert "'=HYPERLINK" in body


class TestBodyCaps:

    async def test_report_description_capped(self, client, student_user, admin_user):
        pid = await _seed_post(admin_user.id)
        r = await client.post(
            f"/api/v1/posts/{pid}/report",
            json={"reason": "spam", "description": "x" * 1001},
            headers=auth_header(_token(student_user)),
        )
        assert r.status_code == 422

    async def test_price_upper_bound(self, client, student_user):
        r = await client.post(
            "/api/v1/posts",
            json={"post_type": "second_hand", "content": "出", "price": 1e12},
            headers=auth_header(_token(student_user)),
        )
        assert r.status_code == 422

    async def test_tag_ids_capped(self, client, student_user):
        r = await client.post(
            "/api/v1/posts",
            json={"post_type": "general", "content": "帖", "tag_ids": list(range(11))},
            headers=auth_header(_token(student_user)),
        )
        assert r.status_code == 422


class TestLegacyVerificationRetired:

    async def test_password_endpoint_is_gone(self, client, student_token):
        r = await client.post(
            "/api/v1/auth/verify",
            json={"student_id": "2024001", "password": "x" * 101},
            headers=auth_header(student_token),
        )
        assert r.status_code == 410


class TestWechatScoping:

    async def test_contact_wechat_only_for_trade_posts(self, client, student_user, admin_user):
        """交易帖（second_hand）向其他学生返回 contact_wechat；general 帖不返回。"""
        import uuid as _uuid
        async with TestSession() as db:  # fixture 用户默认无微信，补上；再建一个旁观学生
            u = await db.get(User, student_user.id)
            u.wechat_id = "wx_test_contact"
            bystander = User(openid=f"by_{_uuid.uuid4().hex[:8]}", nickname="旁观学生",
                             role="student", is_verified=True)
            db.add(bystander)
            await db.commit()
            await db.refresh(bystander)
        trade_pid = await _seed_post(student_user.id, post_type="second_hand")
        general_pid = await _seed_post(student_user.id, post_type="general")
        headers = auth_header(_token(bystander))

        r_trade = await client.get(f"/api/v1/posts/{trade_pid}", headers=headers)
        assert r_trade.status_code == 200
        assert r_trade.json()["data"]["contact_wechat"] == "wx_test_contact"

        r_general = await client.get(f"/api/v1/posts/{general_pid}", headers=headers)
        assert r_general.status_code == 200
        assert r_general.json()["data"]["contact_wechat"] is None

    async def test_author_always_sees_own_contact(self, client, student_user):
        async with TestSession() as db:
            u = await db.get(User, student_user.id)
            u.wechat_id = "wx_test_contact"
            await db.commit()
        pid = await _seed_post(student_user.id, post_type="general")
        r = await client.get(f"/api/v1/posts/{pid}", headers=auth_header(_token(student_user)))
        assert r.json()["data"]["contact_wechat"] == "wx_test_contact"
