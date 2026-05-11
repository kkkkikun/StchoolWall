from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_posts():
    """获取帖子列表 - GET /api/v1/posts"""
    return {"code": 0, "data": {"items": [], "next_cursor": None, "has_more": False}}


@router.post("")
async def create_post():
    """发布帖子 - POST /api/v1/posts"""
    return {"code": 0, "message": "success"}


@router.get("/{post_id}")
async def get_post(post_id: int):
    """获取帖子详情 - GET /api/v1/posts/{post_id}"""
    return {"code": 0, "data": {}}


@router.post("/{post_id}/report")
async def report_post(post_id: int):
    """举报帖子 - POST /api/v1/posts/{post_id}/report"""
    return {"code": 0, "message": "举报成功，管理员将尽快核实"}
