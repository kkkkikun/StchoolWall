from urllib.parse import urlparse
from pydantic import Field
from pydantic_settings import BaseSettings

PLACEHOLDER_JWT_SECRETS = {"your_super_secret_key_change_me"}

class Settings(BaseSettings):
    ENVIRONMENT: str = "production"
    # 部署环境标记：production 是真生产；staging 是预发布/内测。
    # 仓库既有的 rollout.sh 用它区分是否要求人工发布审批。
    # 内测专用的放宽开关只在 staging 下生效，避免真生产误开。
    DEPLOY_ENVIRONMENT: str = "production"
    BUILD_REVISION: str = "development"
    DATABASE_URL: str = "postgresql+asyncpg://eywall:eywall123@localhost:5432/ey_wall"
    DB_POOL_SIZE: int = Field(10, ge=1, le=100)
    DB_MAX_OVERFLOW: int = Field(10, ge=0, le=100)
    DB_POOL_TIMEOUT: int = 10
    DB_STATEMENT_TIMEOUT_MS: int = 10000
    REDIS_URL: str = "redis://localhost:6379/0"
    TEST_DATABASE_URL: str = ""
    TEST_REDIS_URL: str = ""
    JWT_SECRET: str = "your_super_secret_key_change_me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = Field(15, ge=1, le=15)
    REFRESH_EXPIRE_DAYS: int = Field(30, ge=1, le=30)
    WECHAT_APP_ID: str = ""
    WECHAT_APP_SECRET: str = ""
    WECHAT_MP_APP_ID: str = ""
    WECHAT_MP_APP_SECRET: str = ""
    MODERATION_FAIL_OPEN: bool = False
    PUBLISHING_ENABLED: bool = True
    DEV_LOGIN_ENABLED: bool = False
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:5174"
    ADMIN_TOKEN_EXPIRE_HOURS: int = 1
    ADMIN_MFA_ENCRYPTION_KEY: str = ""
    STATIC_BASE_DIR: str = "static"
    PRIVATE_MEDIA_DIR: str = "private-media"
    # 备份状态文件（deploy/backup.sh 写、deploy/backup_status.py 维护）：只含时间戳
    # 与计数，用来把备份新鲜度与备份失败接成可抓取的指标。生产里由 compose 以
    # 只读方式挂进容器；读不到就按「状态未知」记。
    BACKUP_STATUS_FILE: str = "backup-status/backup_status.json"
    MEDIA_MAX_PIXELS: int = 25000000
    MEDIA_MAX_BYTES: int = 10485760
    STORAGE_PROVIDER: str = "local"
    CF_R2_ACCOUNT_ID: str = ""
    CF_R2_ACCESS_KEY: str = ""
    CF_R2_SECRET_KEY: str = ""
    CF_R2_BUCKET: str = ""
    CF_R2_PUBLIC_URL: str = ""
    COS_SECRET_ID: str = ""
    COS_SECRET_KEY: str = ""
    COS_REGION: str = "ap-guangzhou"
    COS_BUCKET: str = ""
    COS_ENDPOINT: str = ""
    COS_PUBLIC_BASE_URL: str = ""
    TENCENT_SECRET_ID: str = ""
    TENCENT_SECRET_KEY: str = ""
    TENCENT_REGION: str = "ap-guangzhou"
    TENCENT_BIZ_TYPE: str = ""
    STUDENT_VERIFICATION_ENABLED: bool = False
    VERIFICATION_SCHOOL_ID: str = "pilot"
    VERIFICATION_SCHOOL_NAME: str = "本校"
    VERIFICATION_FINGERPRINT_KEY: str = ""
    VERIFICATION_FINGERPRINT_KEY_VERSION: str = "v1"
    VERIFICATION_FINGERPRINT_PREVIOUS_KEYS: str = "{}"
    VERIFICATION_PRIVATE_DIR: str = "private-verifications"
    VERIFICATION_STORAGE_PROVIDER: str = "local"
    VERIFICATION_COS_BUCKET: str = ""
    # 内测/预发布环境的显式逃生开关：允许学生证照片存在本机私有目录。
    # 生产环境必须留空 —— 那里的红线是学籍证件 PII 不得落进非私有桶。
    # 打开这个开关等于声明"这台机器上的证件材料只在内测范围内存放"，
    # 责任在部署者，不改变任何其他生产闸门（/static 仍然不公开挂载）。
    VERIFICATION_ALLOW_LOCAL_IN_PRODUCTION: bool = False
    # 内测开关一：允许未完成学生证认证的 guest 参与写操作（发帖、评论、
    # 改资料、点赞收藏等）。生产环境必须为 false —— 那里的 student 身份
    # 是学生证人工核验的结果，代表"这个人确实是我们学校的人"。
    ALLOW_GUEST_INTERACTION: bool = False
    # 内测开关二：把审核结论里的"需人工复核"自动降级为通过。
    # 命中敏感词被拒的内容仍然拒绝，内容安全底线不变。
    # 生产环境必须为 false —— 那里的 review 意味着机器判不了、需要人来定。
    AUTO_APPROVE_MODERATION: bool = False
    ZHENGFANG_BASE_URL: str = ""
    ZHENGFANG_TEST_STUDENT_ID: str = ""
    ZHENGFANG_TEST_PASSWORD: str = ""
    # 内部测试反馈通道
    FEEDBACK_TEST_CODE: str = ""
    FEEDBACK_WEBHOOK_URL: str = ""
    FEEDBACK_WEBHOOK_KIND: str = "generic"
    FEEDBACK_WEBHOOK_SECRET: str = ""
    FEEDBACK_ADMIN_BASE_URL: str = ""
    FEEDBACK_PRIVATE_DIR: str = "private-feedback"
    model_config = {"env_file": ".env", "extra": "ignore"}

settings = Settings()


def is_test_deployment() -> bool:
    """是否是预发布/内测部署（DEPLOY_ENVIRONMENT=staging）。

    内测专用的放宽开关（guest 参与写操作、审核自动通过、学生证存本机）
    只在这个环境下生效。真生产部署无法误开这些闸门。
    """
    return settings.DEPLOY_ENVIRONMENT.strip().lower() == "staging"

def validate_security_config() -> None:
    if settings.ENVIRONMENT not in {"production", "development", "test"}:
        raise RuntimeError("ENVIRONMENT 必须为 production/development/test")
    if settings.ENVIRONMENT != "production":
        return
    secret = settings.JWT_SECRET
    if (not secret or secret in PLACEHOLDER_JWT_SECRETS or len(secret) < 32
            or any(marker in secret.upper() for marker in ("CHANGE_ME", "REPLACE_"))):
        raise RuntimeError("JWT_SECRET 未配置或仍为占位符/过短（需 ≥32 字符）")
    if not settings.DATABASE_URL or "CHANGE_ME" in settings.DATABASE_URL or ":eywall123@" in settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL 未配置或仍为默认/占位密码")
    if not urlparse(settings.REDIS_URL).password or "CHANGE_ME" in settings.REDIS_URL:
        raise RuntimeError("REDIS_URL 必须配置鉴权密码")
    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    if not origins or any(not o.startswith("https://") or "*" in o or "localhost" in o for o in origins):
        raise RuntimeError("CORS_ORIGINS 必须为正式 HTTPS 域名白名单")
    if settings.MODERATION_FAIL_OPEN or settings.DEV_LOGIN_ENABLED:
        raise RuntimeError("生产禁止审核失败放行和开发登录")
    if not is_test_deployment():
        # 真生产部署（DEPLOY_ENVIRONMENT=production）不得开启任何内测放宽开关。
        relaxed = {
            "ALLOW_GUEST_INTERACTION": settings.ALLOW_GUEST_INTERACTION,
            "AUTO_APPROVE_MODERATION": settings.AUTO_APPROVE_MODERATION,
            "VERIFICATION_ALLOW_LOCAL_IN_PRODUCTION": settings.VERIFICATION_ALLOW_LOCAL_IN_PRODUCTION,
        }
        enabled = [name for name, value in relaxed.items() if value]
        if enabled:
            raise RuntimeError(
                "真生产部署禁止开启内测放宽开关: " + ", ".join(sorted(enabled))
                + "；这些开关只在 DEPLOY_ENVIRONMENT=staging 时生效"
            )
    if settings.STUDENT_VERIFICATION_ENABLED:
        import json
        keys = {settings.VERIFICATION_FINGERPRINT_KEY_VERSION: settings.VERIFICATION_FINGERPRINT_KEY}
        try:
            previous = json.loads(settings.VERIFICATION_FINGERPRINT_PREVIOUS_KEYS)
            if not isinstance(previous, dict):
                raise ValueError()
            keys.update(previous)
        except (ValueError, TypeError):
            raise RuntimeError("VERIFICATION_FINGERPRINT_PREVIOUS_KEYS 必须为 JSON 字典") from None
        if any(not isinstance(k, str) or len(k) < 32 or k == secret or
               any(marker in k.upper() for marker in ("CHANGE_ME", "REPLACE_")) for k in keys.values()):
            raise RuntimeError("学籍指纹密钥必须独立且至少32字符")
        if not (settings.VERIFICATION_ALLOW_LOCAL_IN_PRODUCTION and is_test_deployment()):
            if settings.VERIFICATION_STORAGE_PROVIDER != "cos" or not settings.VERIFICATION_COS_BUCKET:
                raise RuntimeError("生产学生证必须使用独立私有 COS 桶")
            if settings.VERIFICATION_COS_BUCKET == settings.COS_BUCKET:
                raise RuntimeError("学生证与公开媒体必须使用不同 COS 桶")
            if not settings.COS_SECRET_ID or not settings.COS_SECRET_KEY:
                raise RuntimeError("学生证 COS 凭证未配置")
    if settings.ZHENGFANG_BASE_URL or settings.ZHENGFANG_TEST_PASSWORD:
        raise RuntimeError("教务密码认证已停用，请删除生产教务配置")

def docs_url() -> str | None:
    return None if settings.ENVIRONMENT == "production" else "/docs"

def redoc_url() -> str | None:
    return None if settings.ENVIRONMENT == "production" else "/redoc"
