"""签到功能测试：每日一签 / 连签推导 / 状态聚合。"""

from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from app.models.checkin import CheckIn
from app.models.user import User
from app.utils.security import create_access_token
from tests.conftest import TestSession, auth_header


def _sh_today() -> date:
    """与后端同口径的上海自然日（测试机时区无关）。"""
    from datetime import datetime, timezone

    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("Asia/Shanghai")).date()


async def _seed_dates(user_id, dates: list[date]):
    async with TestSession() as db:
        for d in dates:
            db.add(CheckIn(user_id=user_id, check_date=d))
        await db.commit()


def _token(user: User) -> str:
    return create_access_token({"sub": str(user.id), "role": user.role})


class TestCheckIn:

    @pytest.mark.asyncio
    async def test_first_checkin(self, client: AsyncClient, student_user: User):
        r = await client.post("/api/v1/user/checkin", headers=auth_header(_token(student_user)))
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["already"] is False
        assert body["data"]["streak_days"] == 1

    @pytest.mark.asyncio
    async def test_duplicate_same_day(self, client: AsyncClient, student_user: User):
        """同一天二签：already=True，连签不变。"""
        token = _token(student_user)
        r1 = await client.post("/api/v1/user/checkin", headers=auth_header(token))
        assert r1.json()["data"]["already"] is False
        r2 = await client.post("/api/v1/user/checkin", headers=auth_header(token))
        body = r2.json()
        assert body["code"] == 0
        assert body["data"]["already"] is True
        assert body["data"]["streak_days"] == 1

    @pytest.mark.asyncio
    async def test_streak_across_days(self, client: AsyncClient, student_user: User):
        """昨天+前天已签，今天签 → 连签 3。"""
        today = _sh_today()
        await _seed_dates(student_user.id, [today - timedelta(days=1), today - timedelta(days=2)])
        r = await client.post("/api/v1/user/checkin", headers=auth_header(_token(student_user)))
        assert r.json()["data"]["streak_days"] == 3

    @pytest.mark.asyncio
    async def test_broken_streak(self, client: AsyncClient, student_user: User):
        """断签两天后再签 → 连签从 1 重新计。"""
        today = _sh_today()
        await _seed_dates(student_user.id, [today - timedelta(days=3), today - timedelta(days=4)])
        r = await client.post("/api/v1/user/checkin", headers=auth_header(_token(student_user)))
        assert r.json()["data"]["streak_days"] == 1

    @pytest.mark.asyncio
    async def test_status_aggregation(self, client: AsyncClient, student_user: User):
        """状态：今日已签/连签/本月/累计（跨月的签到不计入本月）。"""
        today = _sh_today()
        # 连签 3 天（若月初会跨月——本月数按动态预期算，行为仍确定）
        streak_dates = [today - timedelta(days=i) for i in range(3)]
        await _seed_dates(student_user.id, streak_dates + [today - timedelta(days=40)])
        in_month = [d for d in streak_dates if d.month == today.month and d.year == today.year]
        r = await client.get("/api/v1/user/checkin/status", headers=auth_header(_token(student_user)))
        data = r.json()["data"]
        assert data["today_checked"] is True
        assert data["streak_days"] == 3
        assert data["total_count"] == 4
        assert data["month_count"] == len(in_month)

    @pytest.mark.asyncio
    async def test_require_login(self, client: AsyncClient):
        assert (await client.post("/api/v1/user/checkin")).status_code == 401
        assert (await client.get("/api/v1/user/checkin/status")).status_code == 401
