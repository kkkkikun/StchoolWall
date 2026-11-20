"""Fail-closed machine moderation backed by Tencent Cloud TMS and IMS."""
from dataclasses import dataclass
from typing import Literal

from app.utils.tencent_moderation import ModerationProviderError, is_configured, moderate
from app.utils.wechat_client import WechatClientError, load_image_bytes

Verdict = Literal["pass", "reject", "review", "error"]


@dataclass
class ModerationResult:
    verdict: Verdict
    reason: str | None = None
    trace_id: str | None = None


_SEVERITY = {"pass": 0, "error": 1, "review": 2, "reject": 3}


def _strictest(results: list[ModerationResult]) -> ModerationResult:
    return max(results, key=lambda result: _SEVERITY[result.verdict], default=ModerationResult("pass"))


def auto_approve_review(result: ModerationResult) -> ModerationResult:
    """内测模式下把「需人工复核」降级为「通过」。

    只降级 review —— 命中敏感词或被拒绝的内容仍然拒绝，内容安全底线不变。
    生产环境必须留空：那里的 review 意味着机器判不了、需要人来定。
    """
    from app.config import is_test_deployment, settings
    if settings.AUTO_APPROVE_MODERATION and is_test_deployment() and result.verdict == "review":
        return ModerationResult("pass", reason=result.reason or "auto_approved_for_test")
    return result


def _is_configured() -> bool:
    return is_configured()


def _from_wechat_response(data: dict) -> ModerationResult:
    # Retained for historical audit imports; new submissions use Tencent.
    result = data.get("result") or {}
    suggestion = result.get("suggest", "review")
    if suggestion == "risky" or data.get("errcode") == 87014:
        return ModerationResult("reject", reason="legacy_provider_rejected", trace_id=data.get("trace_id"))
    return ModerationResult("pass" if suggestion == "pass" else "review", trace_id=data.get("trace_id"))


def _from_tencent_response(data: dict) -> ModerationResult:
    suggestion = data.get("Suggestion")
    verdict = {"Pass": "pass", "Block": "reject", "Review": "review"}.get(suggestion, "review")
    return ModerationResult(verdict, reason=str(data.get("Label") or "")[:100],
                            trace_id=data.get("RequestId"))


async def check_text(content: str, openid: str = "") -> ModerationResult:
    if not _is_configured():
        return ModerationResult("review", reason="provider_not_configured")
    if not content.strip():
        return ModerationResult("pass")
    try:
        return _from_tencent_response(await moderate("text", content.encode("utf-8")))
    except ModerationProviderError:
        return ModerationResult("error", reason="provider_unavailable")


async def check_image_data(content: bytes) -> ModerationResult:
    if not _is_configured():
        return ModerationResult("review", reason="provider_not_configured")
    try:
        return _from_tencent_response(await moderate("image", content))
    except ModerationProviderError:
        return ModerationResult("error", reason="provider_unavailable")


async def check_images(images: list[str]) -> ModerationResult:
    results = []
    for url in images:
        try:
            content, _ = await load_image_bytes(url)
        except (WechatClientError, ValueError, OSError):
            results.append(ModerationResult("review", reason="media_unavailable"))
            continue
        results.append(await check_image_data(content))
    return _strictest(results)
