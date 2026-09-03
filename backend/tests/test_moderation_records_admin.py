"""审核记录查询 API 测试：鉴权 / 筛选 / 排序 / 分页（只读）。"""
import pytest
from httpx import AsyncClient

from app.models.moderation_record import ModerationRecord
from app.models.post import Post
from app.models.user import User
from tests.conftest import TestSession, auth_header

pytestmark = pytest.mark.asyncio


async def _seed_records(user_id, n: int = 5) -> list[int]:
    """n 条记录：前 2 条 rule/reject（含 matched），其余 wechat/pass。post 需真实存在（FK）。"""
    ids = []
    async with TestSession() as db:
        for i in range(n):
            post = Post(user_id=user_id, post_type="general", content=f"记录测试帖{i}", images=[], status=1)
            db.add(post)
            await db.flush()
            if i < 2:
                r = ModerationRecord(post_id=post.id, source="rule", verdict="reject",
                                     matched=["代考"], reason="命中敏感词：代考（硬违规）")
            else:
                r = ModerationRecord(post_id=post.id, source="wechat", verdict="pass", trace_id="trace_x")
            db.add(r)
            await db.flush()
            ids.append(r.id)
        await db.commit()
    return ids


class TestModerationRecords:

    async def test_requires_console(self, client: AsyncClient, student_user: User, student_token: str):
        """匿名与学生 token 均 403。"""
        r = await client.get("/api/v1/admin/moderation-records")
        assert r.status_code == 403
        r2 = await client.get("/api/v1/admin/moderation-records", headers=auth_header(student_token))
        assert r2.status_code == 403

    async def test_list_default_order(self, client: AsyncClient, console_headers: dict, student_user: User):
        ids = await _seed_records(student_user.id, 5)
        r = await client.get("/api/v1/admin/moderation-records", headers=console_headers)
        data = r.json()["data"]
        assert data["total"] == 5
        assert [item["id"] for item in data["items"]] == list(reversed(ids))  # id 倒序
        first = data["items"][0]
        assert first["source"] == "wechat"
        assert first["verdict"] == "pass"
        assert first["trace_id"] == "trace_x"

    async def test_filters(self, client: AsyncClient, console_headers: dict, student_user: User):
        await _seed_records(student_user.id, 5)
        r = await client.get("/api/v1/admin/moderation-records",
                             params={"verdict": "reject", "source": "rule"}, headers=console_headers)
        data = r.json()["data"]
        assert data["total"] == 2
        assert all(i["verdict"] == "reject" and i["source"] == "rule" for i in data["items"])
        assert data["items"][0]["matched"] == ["代考"]

        first_post_id = data["items"][0]["post_id"]
        r2 = await client.get("/api/v1/admin/moderation-records",
                              params={"post_id": first_post_id}, headers=console_headers)
        assert r2.json()["data"]["total"] == 1

    async def test_pagination(self, client: AsyncClient, console_headers: dict, student_user: User):
        await _seed_records(student_user.id, 5)
        r = await client.get("/api/v1/admin/moderation-records",
                             params={"page": 2, "page_size": 2}, headers=console_headers)
        data = r.json()["data"]
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["page"] == 2
