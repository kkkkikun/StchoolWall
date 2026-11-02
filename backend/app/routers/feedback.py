"""内部测试反馈通道。

提交入口对登录用户直接开放；未登录者需提供内部测试口令。
提交分两步：先建记录拿到上传令牌，再逐张上传截图——
这样 H5 端的 uni.uploadFile（单文件）与 PC 端可以共用同一套接口。
截图落在私有目录，只有管理台能取；提交后异步推送 Webhook 以便快速到达负责人。
"""
import hmac
import json
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import (APIRouter, BackgroundTasks, Depends, File, Form, HTTPException,
                     Query, Request, Response, UploadFile)
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import AdminActor, get_optional_user, require_admin_console
from app.models.feedback import Feedback
from app.models.user import User
from app.services.admin_log import log_admin_action
from app.services.feedback_notify import notify_feedback
from app.services.feedback_storage import (MAX_SCREENSHOTS, delete_screenshot,
                                           read_screenshot, save_screenshot)
from app.utils.rate_limit import RATE_FEEDBACK, RATE_FEEDBACK_ANON, RATE_UPLOAD, check_rate_limit

router = APIRouter()
admin_router = APIRouter()
logger = logging.getLogger(__name__)

CATEGORIES = ("bug", "ui", "feature", "other")
SEVERITIES = ("low", "medium", "high")
STATUSES = ("open", "handling", "resolved", "closed")
MAX_DIAGNOSTIC_BYTES = 32 * 1024
UPLOAD_TOKEN_TTL = timedelta(minutes=30)


class FeedbackCreate(BaseModel):
    category: str = Field(pattern="^(bug|ui|feature|other)$")
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=4000)
    severity: str = Field(default="medium", pattern="^(low|medium|high)$")
    page_url: str = Field(default="", max_length=500)
    route: str = Field(default="", max_length=120)
    viewport: str = Field(default="", max_length=60)
    theme: str = Field(default="", max_length=10)
    app_version: str = Field(default="", max_length=64)
    reporter_name: str = Field(default="", max_length=64)
    test_code: str = Field(default="", max_length=64)
    diagnostics: dict | None = None


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


def _check_test_code(code: str | None) -> None:
    """免登录提交必须命中内部测试口令；未配置口令时该路径整体关闭。"""
    expected = (getattr(settings, "FEEDBACK_TEST_CODE", "") or "").strip()
    if not expected:
        raise HTTPException(status_code=403, detail="未启用内部测试反馈口令，请先登录后再提交")
    if not code or not hmac.compare_digest(code.strip(), expected):
        raise HTTPException(status_code=403, detail="反馈口令不正确")


def _clean_diagnostics(raw: dict | None) -> dict | None:
    if not raw:
        return None
    encoded = json.dumps(raw, ensure_ascii=False).encode("utf-8")
    if len(encoded) > MAX_DIAGNOSTIC_BYTES:
        return {"truncated": True, "note": "诊断数据超出长度上限，已截断"}
    return raw


def _row_payload(row: Feedback, *, with_detail: bool = False, with_token: bool = False) -> dict:
    payload = {
        "id": row.id,
        "category": row.category,
        "severity": row.severity,
        "title": row.title,
        "content": row.content,
        "page_url": row.page_url,
        "route": row.route,
        "viewport": row.viewport,
        "theme": row.theme,
        "app_version": row.app_version,
        "user_agent": row.user_agent,
        "reporter_name": row.reporter_name,
        "status": row.status,
        "note": row.note,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "handled_at": row.handled_at.isoformat() if row.handled_at else None,
        "screenshot_count": len(row.screenshots or []),
    }
    if with_detail:
        payload["diagnostics"] = row.diagnostics
        payload["screenshots"] = row.screenshots or []
        payload["client_ip"] = row.client_ip
    if with_token:
        payload["upload_token"] = row.upload_token
    return payload


@router.post("")
async def submit(
    request: Request,
    background: BackgroundTasks,
    body: FeedbackCreate,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    title = body.title.strip()
    content = body.content.strip()
    if not title or not content:
        raise HTTPException(status_code=400, detail="标题与描述不能为空")

    client_ip = _client_ip(request)
    if user is not None:
        await check_rate_limit(f"rl:feedback:u:{user.id}", *RATE_FEEDBACK)
    else:
        _check_test_code(body.test_code)
        await check_rate_limit(f"rl:feedback:ip:{client_ip}", *RATE_FEEDBACK_ANON)

    row = Feedback(
        user_id=user.id if user else None,
        reporter_name=(user.nickname if user else (body.reporter_name or "").strip()[:64]) or None,
        category=body.category, severity=body.severity, title=title, content=content,
        page_url=(body.page_url or "").strip()[:500] or None,
        route=(body.route or "").strip()[:120] or None,
        user_agent=(request.headers.get("user-agent") or "")[:300] or None,
        viewport=(body.viewport or "").strip()[:60] or None,
        theme=(body.theme or "").strip()[:10] or None,
        app_version=(body.app_version or "").strip()[:64] or None,
        client_ip=client_ip[:45] or None,
        diagnostics=_clean_diagnostics(body.diagnostics),
        upload_token=secrets.token_urlsafe(32),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    background.add_task(_push, row)
    return {"code": 0, "data": _row_payload(row, with_token=True)}


async def _push(row: Feedback) -> None:
    """推送失败只记日志，反馈已经入库。"""
    if not await notify_feedback(row):
        logger.warning("反馈 webhook 推送失败或未配置: feedback_id=%s", row.id)


def _can_upload(row: Feedback, user: User | None, upload_token: str) -> bool:
    if user is not None and row.user_id == user.id:
        return True
    if not upload_token or not row.upload_token:
        return False
    if not hmac.compare_digest(upload_token, row.upload_token):
        return False
    if row.created_at and row.created_at < datetime.now(timezone.utc) - UPLOAD_TOKEN_TTL:
        return False
    return True


@router.post("/{feedback_id}/screenshot")
async def upload_screenshot(
    feedback_id: int,
    request: Request,
    file: UploadFile = File(...),
    upload_token: str = Form(""),
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(Feedback, feedback_id, with_for_update=True)
    if row is None:
        raise HTTPException(status_code=404, detail="反馈不存在")
    if not _can_upload(row, user, upload_token):
        raise HTTPException(status_code=403, detail="无权上传该反馈的截图")
    if len(row.screenshots or []) >= MAX_SCREENSHOTS:
        raise HTTPException(status_code=400, detail=f"截图最多 {MAX_SCREENSHOTS} 张")

    client_ip = _client_ip(request)
    if user is not None:
        await check_rate_limit(f"rl:feedback:u:{user.id}:shot", *RATE_UPLOAD)
    else:
        await check_rate_limit(f"rl:feedback:ip:{client_ip}:shot", *RATE_UPLOAD)

    content = await file.read()
    try:
        item = await save_screenshot(row.id, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    row.screenshots = [*(row.screenshots or []), item]
    await db.commit()
    return {"code": 0, "data": {"id": row.id, "screenshot_count": len(row.screenshots)}}


@router.get("/mine")
async def mine(user: User | None = Depends(get_optional_user),
               page: int = Query(1, ge=1), db: AsyncSession = Depends(get_db)):
    if user is None:
        return {"code": 0, "data": {"items": []}}
    rows = (await db.execute(select(Feedback).where(Feedback.user_id == user.id)
        .order_by(Feedback.created_at.desc(), Feedback.id)
        .offset((page - 1) * 20).limit(20))).scalars()
    return {"code": 0, "data": {"items": [_row_payload(row) for row in rows]}}


@admin_router.get("/stats")
async def stats(db: AsyncSession = Depends(get_db),
                actor: AdminActor = Depends(require_admin_console)):
    rows = (await db.execute(select(Feedback.status, func.count())
        .group_by(Feedback.status))).all()
    counts = {status: count for status, count in rows}
    counts["total"] = sum(counts.values())
    return {"code": 0, "data": counts}


@admin_router.get("")
async def listing(
    status: str = Query("", pattern="^(|open|handling|resolved|closed)$"),
    category: str = Query("", pattern="^(|bug|ui|feature|other)$"),
    keyword: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
    actor: AdminActor = Depends(require_admin_console),
):
    conditions = []
    if status:
        conditions.append(Feedback.status == status)
    if category:
        conditions.append(Feedback.category == category)
    if keyword:
        like = f"%{keyword.strip()}%"
        conditions.append(Feedback.title.ilike(like) | Feedback.content.ilike(like))
    total = await db.scalar(select(func.count()).select_from(Feedback).where(*conditions))
    rows = (await db.execute(select(Feedback).where(*conditions)
        .order_by(Feedback.created_at.desc(), Feedback.id)
        .offset((page - 1) * 20).limit(20))).scalars()
    return {"code": 0, "data": {"items": [_row_payload(row) for row in rows],
                                "total": total, "page": page}}


@admin_router.get("/{feedback_id}")
async def detail(feedback_id: int, db: AsyncSession = Depends(get_db),
                 actor: AdminActor = Depends(require_admin_console)):
    row = await db.get(Feedback, feedback_id)
    if row is None:
        raise HTTPException(status_code=404, detail="反馈不存在")
    return {"code": 0, "data": _row_payload(row, with_detail=True)}


@admin_router.get("/{feedback_id}/screenshot/{index}")
async def screenshot(feedback_id: int, index: int, db: AsyncSession = Depends(get_db),
                     actor: AdminActor = Depends(require_admin_console)):
    row = await db.get(Feedback, feedback_id)
    if row is None:
        raise HTTPException(status_code=404, detail="反馈不存在")
    items = row.screenshots or []
    if index < 0 or index >= len(items):
        raise HTTPException(status_code=404, detail="截图不存在")
    try:
        content = await read_screenshot(items[index]["path"])
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="截图不存在") from None
    return Response(content=content, media_type=items[index].get("content_type", "image/jpeg"),
                    headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@admin_router.put("/{feedback_id}")
async def update(feedback_id: int, request: Request,
                 status: str = Form(""), note: str | None = Form(None),
                 db: AsyncSession = Depends(get_db),
                 actor: AdminActor = Depends(require_admin_console)):
    row = await db.get(Feedback, feedback_id, with_for_update=True)
    if row is None:
        raise HTTPException(status_code=404, detail="反馈不存在")
    if status:
        if status not in STATUSES:
            raise HTTPException(status_code=400, detail="状态不正确")
        row.status = status
    # note 区分「没传」与「传空」：管理员清空备注后保存应当真的清掉
    if note is not None:
        row.note = note[:2000] or None
    row.handled_by = actor.id
    row.handled_at = datetime.now(timezone.utc)
    await log_admin_action(db, actor, "feedback.update", target_type="feedback",
                           target_id=str(row.id), detail={"status": row.status},
                           ip=request.client.host if request.client else None)
    await db.commit()
    return {"code": 0, "data": _row_payload(row, with_detail=True)}
