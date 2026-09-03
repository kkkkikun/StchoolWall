"""签到服务：每日一签 + 连签推导。

- 自然日按 Asia/Shanghai 切（与运营趋势统计同时区）
- 连签不落库，由最近日期集合倒推——收益规则后续怎么改都不用洗数据
"""
from datetime import date, timedelta

from sqlalchemy import cast, func, select, Date as SaDate
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.checkin import CheckIn
from app.models.user import User

TZ_SHANGHAI = "Asia/Shanghai"
# 连签回溯上限：一年来每天签的极端用户也够算（超过一年断签的连签无意义）
MAX_LOOKBACK_DAYS = 366


async def _today(db: AsyncSession) -> date:
    """当前上海自然日。"""
    return (
        await db.execute(select(cast(func.timezone(TZ_SHANGHAI, func.now()), SaDate)))
    ).scalar_one()


async def _dates_of_last_days(db: AsyncSession, user_id, days: int) -> set[date]:
    """用户最近 N 天内的签到日期集合。"""
    since = await _today(db) - timedelta(days=days - 1)
    rows = (
        await db.execute(
            select(CheckIn.check_date).where(
                CheckIn.user_id == user_id, CheckIn.check_date >= since
            )
        )
    ).scalars()
    return set(rows)


def _streak_from(dates: set[date], today: date, today_checked: bool) -> int:
    """从今天（或昨天）往回数连续天数。"""
    cursor = today if today_checked else today - timedelta(days=1)
    streak = 0
    while cursor in dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


async def check_in(db: AsyncSession, user: User) -> dict:
    """今日签到；重复签到返回 already=True（不算错误）。"""
    today = await _today(db)
    exists = (
        await db.execute(
            select(CheckIn.id).where(CheckIn.user_id == user.id, CheckIn.check_date == today)
        )
    ).scalar_one_or_none()
    if exists:
        dates = await _dates_of_last_days(db, user.id, MAX_LOOKBACK_DAYS)
        return {"already": True, "streak_days": _streak_from(dates, today, True), "today": today}

    db.add(CheckIn(user_id=user.id, check_date=today))
    try:
        await db.commit()
    except IntegrityError:
        # 并发双击：唯一约束兜底
        await db.rollback()

    dates = await _dates_of_last_days(db, user.id, MAX_LOOKBACK_DAYS)
    streak = _streak_from(dates, today, True)
    return {"already": False, "streak_days": streak, "today": today}


async def checkin_status(db: AsyncSession, user: User) -> dict:
    """签到状态：今日是否已签/连签/累计/本月天数。"""
    today = await _today(db)
    dates = await _dates_of_last_days(db, user.id, MAX_LOOKBACK_DAYS)
    today_checked = today in dates
    month_prefix = today.replace(day=1)
    return {
        "today_checked": today_checked,
        "streak_days": _streak_from(dates, today, today_checked),
        "month_count": len([d for d in dates if d >= month_prefix]),
        "total_count": (
            await db.execute(
                select(func.count()).select_from(CheckIn).where(CheckIn.user_id == user.id)
            )
        ).scalar_one(),
        "today": today,
    }
