"""内容审核：文本 msg_sec_check v2 + 图片 img_sec_check（同步）。

verdict 语义：
- pass   合规 → 帖子过审
- reject 违规 → 帖子封禁 + 通知作者
- review 机器不确定 → 保持待审，进管理后台人工队列
- error  网络/配额故障 → 上层重试，耗尽后按 MODERATION_FAIL_OPEN 降级
"""
import logging
from dataclasses import dataclass
from typing import Literal

from app.config import settings
from app.utils.wechat_client import (
    WechatClientError,
    img_sec_check,
    load_image_bytes,
    msg_sec_check,
)

logger = logging.getLogger(__name__)

Verdict = Literal["pass", "reject", "review", "error"]


@dataclass
class ModerationResult:
    verdict: Verdict
    reason: str | None = None
    trace_id: str | None = None


# verdict 严重度排序（取最严用）
_SEVERITY = {"pass": 0, "error": 1, "review": 2, "reject": 3}


def _strictest(results: list[ModerationResult]) -> ModerationResult:
    """多结果取最严（reject > review > error > pass）。"""
    return max(results, key=lambda r: _SEVERITY[r.verdict])


def _from_wechat_response(data: dict) -> ModerationResult:
    """微信 v2 响应 → ModerationResult。"""
    result = data.get("result") or {}
    suggest = result.get("suggest", "pass")
    trace_id = data.get("trace_id")
    if suggest == "risky" or data.get("errcode") == 87014:
        return ModerationResult("reject", reason=f"内容违规 label={result.get('label')}", trace_id=trace_id)
    if suggest == "review":
        return ModerationResult("review", reason="机器不确定，待人工", trace_id=trace_id)
    return ModerationResult("pass", trace_id=trace_id)


def _is_configured() -> bool:
    """门禁：测试环境或未配置时直接放行（不调微信）。"""
    return (
        settings.ENVIRONMENT != "test"
        and bool(settings.WECHAT_APP_ID)
        and bool(settings.WECHAT_APP_SECRET)
    )


async def _check_text_via_wechat(content: str, openid: str) -> ModerationResult:
    data = await msg_sec_check(content, openid)
    return _from_wechat_response(data)


async def check_text(content: str, openid: str) -> ModerationResult:
    """文本审核。openid 是 msg_sec_check v2 必填（用户身份维度风控）。"""
    if not _is_configured():
        return ModerationResult("pass")
    if not content.strip():
        return ModerationResult("pass")
    try:
        return await _check_text_via_wechat(content, openid)
    except WechatClientError as e:
        logger.error("文本审核调用失败: %s", e)
        return ModerationResult("error", reason=str(e))


async def _check_images_via_wechat(images: list[str]) -> ModerationResult:
    results: list[ModerationResult] = []
    for url in images:
        try:
            data_bytes, filename = await load_image_bytes(url)
        except WechatClientError as e:
            # 超过 1M / 下载失败 → 交给人工判断，不直接拒绝
            logger.error("图片获取失败（转人工）: %s", e)
            results.append(ModerationResult("review", reason=str(e)))
            continue
        data = await img_sec_check(data_bytes, filename)
        r = _from_wechat_response(data)
        # v1 语义 errcode=87014 在 _from_wechat_response 已覆盖
        results.append(r)
    return _strictest(results)


async def check_images(images: list[str]) -> ModerationResult:
    """图片审核（多图取最严）。"""
    if not _is_configured():
        return ModerationResult("pass")
    if not images:
        return ModerationResult("pass")
    try:
        return await _check_images_via_wechat(images)
    except WechatClientError as e:
        logger.error("图片审核调用失败: %s", e)
        return ModerationResult("error", reason=str(e))
