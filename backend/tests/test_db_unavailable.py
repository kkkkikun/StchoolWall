"""数据库不可达时的错误码语义回归测试。

背景（openspec/specs/optimization/spec.md「PostgreSQL 完全不可达时写路径返回 500
而非 503」条目）：数据库连接被拒时 SQLAlchemy 抛出的 ConnectionRefusedError 是
OSError 子类、不是 SQLAlchemyError，main.py 的 database_error 处理器接不住它，
异常一路落到 request_context 中间件的兜底 500 分支。依赖不可用被报成 500 而不是
503，与 Redis 不可用时的 503 语义不一致。

本文件固定三条行为：
1. 写路径在数据库连接失败时返回 503「数据服务暂时不可用，请稍后重试」，不是 500；
2. 就绪探针在数据库不可达时仍返回 503、存活探针仍返回 200；
3. 与依赖无关的 OSError（如文件读写失败）不被误判成依赖不可用，仍按内部错误 500 处理。
"""
import pytest
from httpx import AsyncClient

from app.database import get_db
from app.main import app
from tests.conftest import auth_header

pytestmark = pytest.mark.asyncio

DB_UNAVAILABLE_MESSAGE = "数据服务暂时不可用，请稍后重试"


class _UnavailableSession:
    """数据库不可达时的假会话：任何一次数据库访问都抛出连接层 OSError。"""

    def __init__(self, exc: BaseException):
        self._exc = exc

    async def get(self, *args, **kwargs):
        raise self._exc

    async def execute(self, *args, **kwargs):
        raise self._exc

    async def commit(self):
        raise self._exc

    async def refresh(self, *args, **kwargs):
        raise self._exc


def _override_db_with(exc: BaseException):
    async def _get_unavailable_db():
        yield _UnavailableSession(exc)

    app.dependency_overrides[get_db] = _get_unavailable_db


async def test_write_path_returns_503_when_database_connection_refused(client: AsyncClient, student_token: str):
    """数据库连接被拒时写路径必须返回 503，而不是兜底的 500。"""
    _override_db_with(ConnectionRefusedError(111, "Connection refused"))

    response = await client.post(
        "/api/v1/posts",
        json={"post_type": "general", "content": "数据库不可达时的写路径"},
        headers=auth_header(student_token),
    )

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == 503
    assert body["message"] == DB_UNAVAILABLE_MESSAGE


async def test_health_probes_report_database_unavailable(client: AsyncClient, monkeypatch):
    """数据库不可达时就绪探针仍 503、存活探针仍 200。"""
    import app.main as main_module

    class _BoomSessionFactory:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            raise ConnectionRefusedError(111, "Connection refused")

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(main_module, "async_session", _BoomSessionFactory)

    ready = await client.get("/health/ready")
    live = await client.get("/health/live")

    assert ready.status_code == 503
    assert ready.json()["status"] == "unavailable"
    assert live.status_code == 200


async def test_unrelated_os_error_stays_internal_error(client: AsyncClient, student_token: str):
    """与依赖无关的 OSError（文件读写失败）不应被误判成依赖不可用。"""
    _override_db_with(PermissionError(13, "Permission denied"))

    response = await client.post(
        "/api/v1/posts",
        json={"post_type": "general", "content": "与数据库无关的 OSError"},
        headers=auth_header(student_token),
    )

    assert response.status_code == 500
    assert response.json()["message"] == "服务暂时不可用"
