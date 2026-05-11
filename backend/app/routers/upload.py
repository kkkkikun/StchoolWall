from fastapi import APIRouter

router = APIRouter()


@router.get("/config")
async def get_upload_config():
    """获取上传配置与凭证 - GET /api/v1/upload/config"""
    return {"code": 0, "data": {}}


@router.post("/direct")
async def direct_upload():
    """本地存储直接上传 - POST /api/v1/upload/direct"""
    return {"code": 0, "message": "success"}
