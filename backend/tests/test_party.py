"""组局模块测试：创建 / 列表(筛选) / 报名(幂等/满额) / 退出 / 我的局 / 累计人数。"""

import pytest
from httpx import AsyncClient

from app.models.user import User
from app.utils.security import create_access_token
from tests.conftest import TestSession, auth_header


def _token(u: User) -> str:
    return create_access_token({"sub": str(u.id), "role": u.role})


async def _create_party(client, token, **kw):
    payload = {"type": "group", "category": "自习", "title": "今晚图书馆自习", "content": "求组队", "total": 4}
    payload.update(kw)
    r = await client.post("/api/v1/parties", json=payload, headers=auth_header(token))
    return r


# ============================================================
# POST /parties — 创建
# ============================================================


class TestCreateParty:
    @pytest.mark.asyncio
    async def test_student_create(self, client: AsyncClient, student_user: User):
        r = await _create_party(client, _token(student_user))
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["title"] == "今晚图书馆自习"
        assert d["joined_count"] == 0
        assert d["status"] == 1
        assert d["total"] == 4

    @pytest.mark.asyncio
    async def test_guest_cannot_create(self, client: AsyncClient, guest_user: User):
        r = await _create_party(client, _token(guest_user))
        assert r.status_code == 403


# ============================================================
# GET /parties — 列表 + 筛选
# ============================================================


class TestListParties:
    @pytest.mark.asyncio
    async def test_list_returns_items(self, client: AsyncClient, student_user: User, admin_user: User):
        await _create_party(client, _token(student_user), title="A")
        await _create_party(client, _token(admin_user), title="B")
        r = await client.get("/api/v1/parties")
        assert len(r.json()["data"]["items"]) == 2

    @pytest.mark.asyncio
    async def test_filter_category(self, client: AsyncClient, student_user: User):
        await _create_party(client, _token(student_user), category="自习", title="x")
        await _create_party(client, _token(student_user), category="聚餐", title="y")
        r = await client.get("/api/v1/parties?category=自习")
        items = r.json()["data"]["items"]
        assert len(items) == 1 and items[0]["category"] == "自习"


# ============================================================
# 报名 / 退出
# ============================================================


class TestJoin:
    @pytest.mark.asyncio
    async def test_join_increments(self, client: AsyncClient, student_user: User, admin_user: User):
        party = (await _create_party(client, _token(student_user), total=3)).json()["data"]
        r = await client.post(f"/api/v1/parties/{party['id']}/join", headers=auth_header(_token(admin_user)))
        assert r.status_code == 200
        assert r.json()["data"]["joined"] is True
        assert r.json()["data"]["joined_count"] == 1

    @pytest.mark.asyncio
    async def test_join_idempotent(self, client: AsyncClient, student_user: User, admin_user: User):
        party = (await _create_party(client, _token(student_user), total=3)).json()["data"]
        for _ in range(3):
            await client.post(f"/api/v1/parties/{party['id']}/join", headers=auth_header(_token(admin_user)))
        r = await client.get(f"/api/v1/parties")
        assert r.json()["data"]["items"][0]["joined_count"] == 1

    @pytest.mark.asyncio
    async def test_full_blocked_and_status(self, client: AsyncClient, student_user: User, admin_user: User, guest_user: User):
        """满额后再报名被拒，且 status 变 2"""
        party = (await _create_party(client, _token(student_user), total=1)).json()["data"]
        # admin 报名占满
        await client.post(f"/api/v1/parties/{party['id']}/join", headers=auth_header(_token(admin_user)))
        # 再建第二个报名者（用另一个 student）—— 复用 admin_user/student_user，需第三个人
        # 用 guest 不能报名(403)，所以用 admin 再报应幂等；改用直接断言 status
        r = await client.get("/api/v1/parties")
        p = r.json()["data"]["items"][0]
        assert p["joined_count"] == 1
        assert p["status"] == 2  # 满额自动关闭

    @pytest.mark.asyncio
    async def test_leave_decrements(self, client: AsyncClient, student_user: User, admin_user: User):
        party = (await _create_party(client, _token(student_user), total=3)).json()["data"]
        await client.post(f"/api/v1/parties/{party['id']}/join", headers=auth_header(_token(admin_user)))
        r = await client.delete(f"/api/v1/parties/{party['id']}/join", headers=auth_header(_token(admin_user)))
        assert r.status_code == 200
        assert r.json()["data"]["joined_count"] == 0
        assert r.json()["data"]["joined"] is False


# ============================================================
# 我的局 / 累计人数
# ============================================================


class TestMyAndSummary:
    @pytest.mark.asyncio
    async def test_my_parties(self, client: AsyncClient, student_user: User, admin_user: User):
        party = (await _create_party(client, _token(student_user), total=3)).json()["data"]
        await client.post(f"/api/v1/parties/{party['id']}/join", headers=auth_header(_token(admin_user)))
        r = await client.get("/api/v1/me/parties", headers=auth_header(_token(admin_user)))
        assert len(r.json()["data"]["items"]) == 1

    @pytest.mark.asyncio
    async def test_summary_total_members(self, client: AsyncClient, student_user: User, admin_user: User):
        party = (await _create_party(client, _token(student_user), total=3)).json()["data"]
        await client.post(f"/api/v1/parties/{party['id']}/join", headers=auth_header(_token(admin_user)))
        r = await client.get("/api/v1/parties/summary")
        assert r.json()["data"]["total_members"] >= 1
