"""敏感词库管理 API 测试：鉴权 / CRUD / 重复与校验 / 审计 / 筛选分页。"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.admin_log import AdminLog
from app.models.sensitive_word import SensitiveWord
from app.models.user import User
from tests.conftest import TestSession, auth_header

pytestmark = pytest.mark.asyncio


async def _count_words() -> int:
    from sqlalchemy import func
    async with TestSession() as db:
        return (await db.execute(select(func.count()).select_from(SensitiveWord))).scalar() or 0


class TestSensitiveWordsAuth:

    async def test_requires_console(self, client: AsyncClient, student_user: User, student_token: str):
        """匿名返回 401；学生 token 无管理权限返回 403。"""
        r = await client.get("/api/v1/admin/sensitive-words")
        assert r.status_code == 401
        r2 = await client.get("/api/v1/admin/sensitive-words", headers=auth_header(student_token))
        assert r2.status_code == 403


class TestSensitiveWordsCrud:

    async def test_crud_lifecycle(self, client: AsyncClient, console_headers: dict):
        """POST → GET 含新词 → PUT 改级别 → DELETE → 列表为空；缺失 id 404。"""
        r = await client.post("/api/v1/admin/sensitive-words", json={"word": "测试硬词", "level": "hard"},
                              headers=console_headers)
        assert r.status_code == 200
        word_id = r.json()["data"]["id"]

        r2 = await client.get("/api/v1/admin/sensitive-words", headers=console_headers)
        words = [w["word"] for w in r2.json()["data"]["items"]]
        assert "测试硬词" in words

        r3 = await client.put(f"/api/v1/admin/sensitive-words/{word_id}", json={"word": "测试硬词", "level": "gray"},
                              headers=console_headers)
        assert r3.status_code == 200
        r4 = await client.get("/api/v1/admin/sensitive-words", params={"q": "测试硬词"}, headers=console_headers)
        assert r4.json()["data"]["items"][0]["level"] == "gray"

        r5 = await client.delete(f"/api/v1/admin/sensitive-words/{word_id}", headers=console_headers)
        assert r5.status_code == 200
        assert await _count_words() == 0

        # 缺失 id
        r6 = await client.put("/api/v1/admin/sensitive-words/99999", json={"word": "x", "level": "hard"},
                              headers=console_headers)
        assert r6.status_code == 404
        r7 = await client.delete("/api/v1/admin/sensitive-words/99999", headers=console_headers)
        assert r7.status_code == 404

    async def test_duplicate_word_rejected(self, client: AsyncClient, console_headers: dict):
        await client.post("/api/v1/admin/sensitive-words", json={"word": "重复词", "level": "hard"},
                          headers=console_headers)
        r = await client.post("/api/v1/admin/sensitive-words", json={"word": "重复词", "level": "gray"},
                              headers=console_headers)
        assert r.status_code == 400

    async def test_invalid_level_422(self, client: AsyncClient, console_headers: dict):
        r = await client.post("/api/v1/admin/sensitive-words", json={"word": "词", "level": "oops"},
                              headers=console_headers)
        assert r.status_code == 422

    async def test_crud_audit_logged(self, client: AsyncClient, console_headers: dict, console_admin):
        """增改删各写一条 sensitive_word.* 审计。"""
        r = await client.post("/api/v1/admin/sensitive-words", json={"word": "审计词", "level": "hard"},
                              headers=console_headers)
        word_id = r.json()["data"]["id"]
        await client.put(f"/api/v1/admin/sensitive-words/{word_id}", json={"word": "审计词", "level": "gray"},
                         headers=console_headers)
        await client.delete(f"/api/v1/admin/sensitive-words/{word_id}", headers=console_headers)

        async with TestSession() as db:
            logs = (await db.execute(
                select(AdminLog).where(AdminLog.action.like("sensitive_word.%")).order_by(AdminLog.id)
            )).scalars().all()
            assert [l.action for l in logs] == [
                "sensitive_word.create", "sensitive_word.update", "sensitive_word.delete",
            ]
            assert all(l.admin_id == str(console_admin.id) for l in logs)
            assert all(l.target_type == "sensitive_word" for l in logs)

    async def test_list_filters_and_pagination(self, client: AsyncClient, console_headers: dict):
        """q/level 筛选 + 分页切片与 total。"""
        for i in range(25):
            level = "hard" if i % 2 == 0 else "gray"
            await client.post("/api/v1/admin/sensitive-words",
                              json={"word": f"翻页词{i:02d}", "level": level}, headers=console_headers)

        r = await client.get("/api/v1/admin/sensitive-words",
                             params={"page": 2, "page_size": 10}, headers=console_headers)
        data = r.json()["data"]
        assert data["total"] == 25
        assert len(data["items"]) == 10
        # id 倒序：第 2 页首条是第 15 新的
        assert data["items"][0]["word"] == "翻页词14"

        r2 = await client.get("/api/v1/admin/sensitive-words",
                              params={"level": "hard"}, headers=console_headers)
        assert r2.json()["data"]["total"] == 13

        r3 = await client.get("/api/v1/admin/sensitive-words",
                              params={"q": "翻页词0"}, headers=console_headers)
        assert r3.json()["data"]["total"] == 10  # 00-09
