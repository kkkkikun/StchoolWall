"""把新反馈推送到外部 Webhook（飞书 / 企业微信 / 通用 HTTP 接收器）。

推送失败不影响反馈入库：内部测试期间反馈必须先落库，通知只是加速到达。
"""
import hashlib
import hmac
import json
import urllib.error
import urllib.request

from app.config import settings
from app.models.feedback import Feedback

_TIMEOUT_SECONDS = 5
_CONTENT_LIMIT = 600
# 企业微信群机器人 text 消息的 content 上限是 2048 字节（不是字符数）
_WECOM_TEXT_BYTE_LIMIT = 2048


def _diagnostic_summary(diagnostics: dict | None) -> str:
    if not diagnostics:
        return "无"
    errors = diagnostics.get("errors") or []
    api_failures = diagnostics.get("api_failures") or []
    parts = [f"页面错误 {len(errors)} 条", f"失败请求 {len(api_failures)} 条"]
    detail = [str(item.get("message", ""))[:120] for item in errors[:3]]
    detail += [f"{item.get('method', '')} {item.get('url', '')} → {item.get('status', '')}"[:120]
               for item in api_failures[:3]]
    if detail:
        parts.append("；".join(detail))
    return "，".join(parts)


def build_text(row: Feedback) -> str:
    """三种载荷格式共用同一段可读文本。"""
    lines = [
        f"【校园墙反馈·{row.category}】{row.title}",
        f"严重程度：{row.severity}　状态：{row.status}",
        f"提交人：{row.reporter_name or ('用户 ' + str(row.user_id)[:8] if row.user_id else '匿名测试员')}",
        f"时间：{row.created_at.isoformat() if row.created_at else ''}",
    ]
    if row.page_url:
        lines.append(f"页面：{row.page_url}")
    if row.route:
        lines.append(f"路由：{row.route}")
    if row.viewport:
        lines.append(f"视口：{row.viewport}")
    if row.theme:
        lines.append(f"主题：{row.theme}")
    if row.app_version:
        lines.append(f"端：{row.app_version}")
    content = (row.content or "").strip()
    if len(content) > _CONTENT_LIMIT:
        content = content[:_CONTENT_LIMIT] + "…"
    lines.append(f"描述：{content}")
    lines.append(f"诊断：{_diagnostic_summary(row.diagnostics)}")
    if row.screenshots:
        lines.append(f"截图：{len(row.screenshots)} 张（请在管理台查看）")
    if getattr(settings, "FEEDBACK_ADMIN_BASE_URL", ""):
        lines.append(f"处理入口：{settings.FEEDBACK_ADMIN_BASE_URL.rstrip('/')}/feedback")
    return "\n".join(lines)


def _truncate_utf8(text: str, limit_bytes: int) -> str:
    """按字节截断且不切断多字节字符。省略号本身也占字节，要先预留。"""
    encoded = text.encode("utf-8")
    if len(encoded) <= limit_bytes:
        return text
    if limit_bytes <= 3:
        return encoded[:limit_bytes].decode("utf-8", errors="ignore")
    # 先给结尾的省略号留出 3 字节，再解码——否则切在多字节字符中间会超限
    return encoded[:limit_bytes - 3].decode("utf-8", errors="ignore") + "…"


def build_payload(row: Feedback) -> dict:
    kind = (getattr(settings, "FEEDBACK_WEBHOOK_KIND", "generic") or "generic").lower()
    text = build_text(row)
    if kind == "feishu":
        return {"msg_type": "text", "content": {"text": text}}
    if kind in {"wecom", "wechat"}:
        return {"msgtype": "text", "text": {"content": _truncate_utf8(text, _WECOM_TEXT_BYTE_LIMIT)}}
    return {
        "type": "feedback",
        "id": row.id,
        "category": row.category,
        "severity": row.severity,
        "status": row.status,
        "title": row.title,
        "content": row.content,
        "page_url": row.page_url,
        "route": row.route,
        "reporter": row.reporter_name,
        "user_id": str(row.user_id) if row.user_id else None,
        "viewport": row.viewport,
        "theme": row.theme,
        "app_version": row.app_version,
        "user_agent": row.user_agent,
        "diagnostics": row.diagnostics,
        "screenshot_count": len(row.screenshots or []),
        "text": text,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _sign(body: bytes) -> str | None:
    secret = getattr(settings, "FEEDBACK_WEBHOOK_SECRET", "")
    if not secret:
        return None
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _check_response(status: int, raw: bytes) -> None:
    """企微与飞书在业务失败时仍返回 HTTP 200，错误码在 body 里，必须自己判。"""
    try:
        body = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return
    if not isinstance(body, dict):
        return
    # 企微：{"errcode": 0, "errmsg": "ok"}；飞书：{"code": 0, "msg": "success"}
    code = body.get("errcode", body.get("code", 0))
    if isinstance(code, int) and code != 0:
        raise ValueError(f"webhook 返回错误码 {code}: {body.get('errmsg') or body.get('msg') or ''}")


def _post(url: str, body: bytes) -> None:
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json; charset=utf-8")
    signature = _sign(body)
    if signature:
        request.add_header("X-Feedback-Signature", signature)
    with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
        _check_response(response.status, response.read())


async def notify_feedback(row: Feedback) -> bool:
    """返回是否推送成功；未配置 Webhook 时视为无需推送。"""
    url = (getattr(settings, "FEEDBACK_WEBHOOK_URL", "") or "").strip()
    if not url:
        return False
    import asyncio

    body = json.dumps(build_payload(row), ensure_ascii=False).encode("utf-8")
    try:
        await asyncio.to_thread(_post, url, body)
        return True
    except (urllib.error.URLError, OSError, ValueError):
        return False
