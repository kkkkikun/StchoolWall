"""Redis 固定窗口限流。

原子性：SET NX 先建带 TTL 的键再 INCR——消灭"INCR 后进程死亡导致
无 TTL 永久限流键"的窗口（原 INCR+EXPIRE 两步写法的缺陷）。
"""
from fastapi import HTTPException
from redis.asyncio import Redis

from app.utils.redis import redis_client

# 业务限流阈值 (max_requests, window_seconds)：写操作按用户维度，叠加在 IP 层之外
RATE_POST_CREATE = (10, 3600)    # 发帖 10 次/小时
RATE_COMMENT = (30, 600)         # 评论 30 次/10 分钟
RATE_REPORT = (10, 600)          # 举报 10 次/10 分钟（防举报轰炸管理队列）
RATE_UPLOAD = (30, 3600)         # 上传 30 次/小时
RATE_FEEDBACK = (20, 3600)       # 反馈 20 次/小时（登录用户）
RATE_FEEDBACK_ANON = (5, 3600)   # 反馈 5 次/小时（免登录口令，按 IP）
LOGIN_USER_RATE = (5, 600)       # 管理台按用户名连续失败 5 次/10 分钟


async def check_rate_limit(key: str, max_requests: int, window_seconds: int) -> None:
    """超限抛 429。计数键自建立即带 TTL。"""
    await redis_client.set(key, 0, ex=window_seconds, nx=True)
    current = await redis_client.incr(key)
    if current > max_requests:
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")


async def get_rate(key: str) -> int:
    return int(await redis_client.get(key) or 0)


async def incr_rate(key: str, window_seconds: int) -> None:
    """手动累加计数（如登录失败次数），键同样自带 TTL。"""
    await redis_client.set(key, 0, ex=window_seconds, nx=True)
    await redis_client.incr(key)


async def clear_rate(key: str) -> None:
    await redis_client.delete(key)
