"""图片内容审核工具

MVP 阶段使用占位实现，直接返回 True。
生产环境可替换为微信 img_sec_check 或第三方 API。
"""

from app.config import settings


async def check_images(images: list[str]) -> bool:
    """检查图片是否合规

    Args:
        images: 图片 URL 列表

    Returns:
        True=全部合规, False=含有违规内容
    """
    # MVP: 占位实现，无图片或默认通过
    if not images:
        return True

    # TODO: 生产环境调用微信内容安全 API
    # https://developers.weixin.qq.com/miniprogram/dev/api-backend/open-api/sec-check/imgSecCheck.html

    # 占位：默认返回通过
    return True


async def check_text(content: str) -> bool:
    """检查文本是否合规（可选）

    Args:
        content: 帖子正文

    Returns:
        True=合规, False=违规
    """
    # TODO: 可选实现文本过滤
    return True
