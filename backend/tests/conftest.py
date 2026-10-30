import os
from urllib.parse import urlparse
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models.admin_user import AdminUser
from app.models.user import User
from app.utils.security import create_access_token

# ---- 测试环境配置 ----
@pytest.fixture(scope="session", autouse=True)
def set_test_environment():
    """设置测试环境变量"""
    original_env = settings.ENVIRONMENT
    # 通过 monkey patch 修改 settings
    settings.ENVIRONMENT = "test"
    yield
    settings.ENVIRONMENT = original_env

# ---- 测试数据库（NullPool 避免跨事件循环连接复用） ----
TEST_DB_URL = os.environ.get("TEST_DATABASE_URL") or settings.TEST_DATABASE_URL
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL") or settings.TEST_REDIS_URL
if not TEST_DB_URL or not urlparse(TEST_DB_URL).path.endswith("_test"):
    raise RuntimeError("TEST_DATABASE_URL must explicitly target a disposable *_test database")
if not TEST_REDIS_URL or urlparse(TEST_REDIS_URL).path not in {"/13", "/14", "/15"}:
    raise RuntimeError("TEST_REDIS_URL must explicitly select isolated test Redis DB 13/14/15")
if TEST_DB_URL == settings.DATABASE_URL and settings.ENVIRONMENT != "test":
    raise RuntimeError("Refusing to clean a non-test application database")
test_engine = create_async_engine(TEST_DB_URL, echo=False, poolclass=NullPool)
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def test_redis() -> AsyncGenerator[Redis, None]:
    """每个测试独立的 Redis 客户端"""
    r = Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    yield r
    await r.flushdb()
    await r.aclose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_before_test(test_redis: Redis):
    """每个测试之前清空所有表，并注入当前循环的 Redis 客户端"""
    import app.utils.rate_limit as rl_module
    import app.utils.redis as redis_module

    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    await test_redis.flushdb()

    # 把当前循环的 Redis 注入到业务模块
    rl_module.redis_client = test_redis
    redis_module.redis_client = test_redis

    yield


# ---- DB Session 注入 ----


async def _get_test_db():
    async with TestSession() as session:
        yield session


# ---- HTTP 测试客户端 ----


@pytest_asyncio.fixture
async def client(monkeypatch) -> AsyncGenerator[AsyncClient, None]:
    import app.main as main_module
    monkeypatch.setattr(main_module, "async_session", TestSession)
    app.dependency_overrides[get_db] = _get_test_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ---- 用户 Fixtures ----


async def _create_user(**kwargs) -> User:
    async with TestSession() as db:
        user = User(**kwargs)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


@pytest_asyncio.fixture
async def guest_user() -> User:
    return await _create_user(
        openid=f"test_guest_{uuid.uuid4().hex[:8]}",
        nickname="游客_测试",
        role="guest",
        is_verified=False,
    )


@pytest_asyncio.fixture
async def student_user() -> User:
    return await _create_user(
        openid=f"test_student_{uuid.uuid4().hex[:8]}",
        nickname="学生_测试",
        role="student",
        is_verified=True,
        student_id=f"2024{uuid.uuid4().hex[:4]}",
        real_name="测试张三",
    )


@pytest_asyncio.fixture
async def admin_user() -> User:
    return await _create_user(
        openid=f"test_admin_{uuid.uuid4().hex[:8]}",
        nickname="管理员_测试",
        role="admin",
        is_verified=True,
        student_id="ADMIN001",
        real_name="管理员",
    )


# ---- Token ----


@pytest.fixture
def guest_token(guest_user: User) -> str:
    return create_access_token({"sub": str(guest_user.id), "role": "guest"})


@pytest.fixture
def student_token(student_user: User) -> str:
    return create_access_token({"sub": str(student_user.id), "role": "student"})


@pytest.fixture
def admin_token(admin_user: User) -> str:
    return create_access_token({"sub": str(admin_user.id), "role": "admin"})


# ---- 管理后台（console）账号 ----


@pytest_asyncio.fixture
async def console_admin() -> AdminUser:
    from app.utils.password import hash_password

    async with TestSession() as db:
        admin = AdminUser(
            username=f"console_admin_{uuid.uuid4().hex[:6]}",
            nickname="后台管理员",
            password_hash=hash_password("Admin12345"),
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
        return admin


@pytest.fixture
def console_token(console_admin: AdminUser) -> str:
    from app.services.admin_auth import issue_console_token

    return issue_console_token(console_admin)


@pytest.fixture
def console_headers(console_token: str) -> dict:
    return {"Authorization": f"Bearer {console_token}"}


# ---- 辅助 ----


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
