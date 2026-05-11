from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile

from app.dependencies import require_role
from app.models.user import User
from app.utils.storage import get_storage_backend, validate_file

router = APIRouter()


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
    path: str = Query(..., min_length=1),
    user: User = Depends(require_role("student", "admin")),
):
    """本地存储直接上传（仅 STORAGE_PROVIDER=local 时使用）"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="缺少文件名")

    err = validate_file(file.filename, file.content_type or "")
    if err:
        raise HTTPException(status_code=400, detail=err)

    from app.utils.storage import MAX_FILE_SIZE

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小超过 10MB 限制")

    backend = get_storage_backend()
    if not hasattr(backend, "save_upload"):
        raise HTTPException(status_code=400, detail="当前存储模式不支持直接上传")

    await file.seek(0)
    public_url = await backend.save_upload(file, path)
    return {"code": 0, "data": {"public_url": public_url}}
