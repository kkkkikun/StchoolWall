from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Environment
    ENVIRONMENT: str = "development"  # development, test, production

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
    MODERATION_FAIL_OPEN: bool = True

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
