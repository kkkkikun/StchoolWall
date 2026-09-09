from pydantic_settings import BaseSettings

# 仓库公开的占位密钥黑名单：生产环境命中即拒绝启动
PLACEHOLDER_JWT_SECRETS = {"your_super_secret_key_change_me"}


class Settings(BaseSettings):
    # Environment（fail-secure：默认按生产对待，dev 需在 .env 显式声明）
    ENVIRONMENT: str = "production"  # development, test, production

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://eywall:eywall123@localhost:5432/ey_wall"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    JWT_SECRET: str = "your_super_secret_key_change_me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 10080  # 7 days

    # WeChat Mini Program
    WECHAT_APP_ID: str = ""
    WECHAT_APP_SECRET: str = ""
    # 内容审核降级策略：True=微信故障时放行（可用性优先），False=保持待审等人工（合规优先）
    MODERATION_FAIL_OPEN: bool = False
    # dev-login 双闸之二：即使 ENVIRONMENT=development 也需显式 true 才暴露一键登录
    DEV_LOGIN_ENABLED: bool = False

    # CORS 白名单（逗号分隔）：H5 预览 + 管理台；小程序原生请求不受 CORS 约束
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:5174"

    # Admin console（独立 Web 管理后台）
    ADMIN_TOKEN_EXPIRE_HOURS: int = 12
    STATIC_BASE_DIR: str = "static"

    # Storage
    STORAGE_PROVIDER: str = "local"  # local, r2, aliyun
    CF_R2_ACCOUNT_ID: str = ""
    CF_R2_ACCESS_KEY: str = ""
    CF_R2_SECRET_KEY: str = ""
    CF_R2_BUCKET: str = ""
    CF_R2_PUBLIC_URL: str = ""

    # Zhengfang Academic System
    ZHENGFANG_BASE_URL: str = ""
    ZHENGFANG_TEST_STUDENT_ID: str = ""
    ZHENGFANG_TEST_PASSWORD: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()


def validate_security_config() -> None:
    """启动安全闸门：生产环境密钥不合格即拒绝启动（fail-fast）。

    覆盖"忘配 .env / env 文件路径解析失败"两类静默降级——两者都会落入默认值，
    而默认密钥是仓库内公开的占位符，等于允许任意 token 伪造。
    """
    if settings.ENVIRONMENT != "production":
        return
    secret = settings.JWT_SECRET
    if not secret or secret in PLACEHOLDER_JWT_SECRETS or len(secret) < 32:
        raise RuntimeError(
            "JWT_SECRET 未配置或仍为占位符/过短（需 ≥32 字符），生产环境拒绝启动。"
            "生成随机密钥：openssl rand -hex 32"
        )


def docs_url() -> str | None:
    """交互式 API 文档地址：生产关闭（防 admin 路由/模型枚举）。"""
    return None if settings.ENVIRONMENT == "production" else "/docs"


def redoc_url() -> str | None:
    return None if settings.ENVIRONMENT == "production" else "/redoc"
