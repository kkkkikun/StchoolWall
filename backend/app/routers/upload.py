import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile

from app.dependencies import require_role
from app.models.user import User
from app.utils.rate_limit import RATE_UPLOAD, check_rate_limit
from app.utils.storage import get_storage_backend, validate_file

router = APIRouter()

# 客户端可声明的上传类别（落盘一级目录），路径其余部分一律服务端生成
UPLOAD_KINDS = ("avatars", "banners", "posts", "parties")


@router.get("/config")
async def get_upload_config(
    filename: str = Query(..., min_length=1),
    content_type: str = Query("image/jpeg"),
    user: User = Depends(require_role("student", "admin")),
):
    """获取上传配置与凭证（按 STORAGE_PROVIDER 下发策略）"""
    err = validate_file(filename, content_type)
    if err:
        raise HTTPException(status_code=400, detail=err)

    backend = get_storage_backend()
    config = await backend.get_upload_config(filename, content_type)
    return {"code": 0, "data": config}


@router.post("/direct")
async def direct_upload(
    file: UploadFile,
    kind: str = Query(..., pattern="^(avatars|banners|posts|parties)$"),
    user: User = Depends(require_role("student", "admin")),
):
    """本地存储直接上传（仅 STORAGE_PROVIDER=local 时使用）。

    安全约束：落盘路径完全由服务端生成（kind 白名单 + 年份 + uuid + 校验过的扩展名），
    客户端不可指定——杜绝任意扩展落盘（存储型 XSS）与覆盖他人文件。
    """
    await check_rate_limit(f"rl:u:{user.id}:upload", *RATE_UPLOAD)

    if not file.filename:
        raise HTTPException(status_code=400, detail="缺少文件名")

    # 扩展名/类型校验对象 = 真实落盘文件（ext 从这里取，路径不自造）
    err = validate_file(file.filename, file.content_type or "")
    if err:
        raise HTTPException(status_code=400, detail=err)

    from app.utils.storage import MAX_FILE_SIZE

    # 流式读取限大小：超限即拒（防整读超大请求体进内存）
    size = 0
    while chunk := await file.read(256 * 1024):
        size += len(chunk)
        if size > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="文件大小超过 10MB 限制")

    backend = get_storage_backend()
    if not hasattr(backend, "save_upload"):
        raise HTTPException(status_code=400, detail="当前存储模式不支持直接上传")

    ext = Path(file.filename).suffix.lower()
    path = f"{kind}/{datetime.now().year}/{uuid.uuid4().hex}{ext}"

    await file.seek(0)
    try:
        public_url = await backend.save_upload(file, path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"code": 0, "data": {"public_url": public_url}}
