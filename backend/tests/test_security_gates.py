"""启动安全闸门测试：密钥校验 / dev-login 双闸 / 生产关文档 / 安全响应头 / CORS 白名单。"""
import pytest
from httpx import AsyncClient

from app.config import settings


class TestValidateSecurityConfig:
    """validate_security_config：仅 production 强校验，其余环境跳过。"""

    def _validate(self):
        from app.config import validate_security_config
        validate_security_config()

    def test_production_placeholder_rejected(self):
        settings.ENVIRONMENT = "production"
        settings.JWT_SECRET = "your_super_secret_key_change_me"
        try:
            with pytest.raises(RuntimeError):
                self._validate()
        finally:
            settings.ENVIRONMENT = "test"
            settings.JWT_SECRET = "test_secret_for_unit_tests_only_not_used_in_ci"

    def test_production_short_secret_rejected(self):
        settings.ENVIRONMENT = "production"
        settings.JWT_SECRET = "short"
        try:
            with pytest.raises(RuntimeError):
                self._validate()
        finally:
            settings.ENVIRONMENT = "test"
            settings.JWT_SECRET = "test_secret_for_unit_tests_only_not_used_in_ci"

    def test_production_empty_secret_rejected(self):
        settings.ENVIRONMENT = "production"
        settings.JWT_SECRET = ""
        try:
            with pytest.raises(RuntimeError):
                self._validate()
        finally:
            settings.ENVIRONMENT = "test"
            settings.JWT_SECRET = "test_secret_for_unit_tests_only_not_used_in_ci"

    def test_production_strong_secret_passes(self):
        settings.ENVIRONMENT = "production"
        settings.JWT_SECRET = "a" * 48
        settings.DATABASE_URL = "postgresql+asyncpg://u:strongpass@db:5432/ey_wall"
        settings.REDIS_URL = "redis://:strongpass@redis:6379/0"
        settings.CORS_ORIGINS = "https://example.edu.cn"
        try:
            self._validate()  # 不抛即通过
        finally:
            settings.ENVIRONMENT = "test"
            settings.JWT_SECRET = "test_secret_for_unit_tests_only_not_used_in_ci"
            settings.DATABASE_URL = "postgresql+asyncpg://eywall:eywall123@localhost:5432/ey_wall"
            settings.REDIS_URL = "redis://localhost:6379/0"
            settings.CORS_ORIGINS = "http://localhost:5173,http://localhost:5174"

    def test_production_default_db_rejected(self):
        settings.ENVIRONMENT = "production"
        settings.JWT_SECRET = "a" * 48
        settings.DATABASE_URL = "postgresql+asyncpg://eywall:eywall123@localhost:5432/ey_wall"
        try:
            with pytest.raises(RuntimeError):
                self._validate()
        finally:
            settings.ENVIRONMENT = "test"
            settings.JWT_SECRET = "test_secret_for_unit_tests_only_not_used_in_ci"

    def test_production_default_redis_rejected(self):
        settings.ENVIRONMENT = "production"
        settings.JWT_SECRET = "a" * 48
        settings.REDIS_URL = "redis://localhost:6379/0"
        try:
            with pytest.raises(RuntimeError):
                self._validate()
        finally:
            settings.ENVIRONMENT = "test"
            settings.JWT_SECRET = "test_secret_for_unit_tests_only_not_used_in_ci"

    def test_production_localhost_cors_rejected(self):
        settings.ENVIRONMENT = "production"
        settings.JWT_SECRET = "a" * 48
        settings.CORS_ORIGINS = "http://localhost:5173"
        try:
            with pytest.raises(RuntimeError):
                self._validate()
        finally:
            settings.ENVIRONMENT = "test"
            settings.JWT_SECRET = "test_secret_for_unit_tests_only_not_used_in_ci"

    def test_dev_environment_skips_check(self):
        """development 不强制（本地快速起步靠 .env 显式配置）。"""
        settings.ENVIRONMENT = "development"
        settings.JWT_SECRET = "your_super_secret_key_change_me"
        try:
            self._validate()
        finally:
            settings.ENVIRONMENT = "test"
            settings.JWT_SECRET = "test_secret_for_unit_tests_only_not_used_in_ci"


class TestDevLoginDoubleGate:
    """dev-login 需 ENVIRONMENT=development 且 DEV_LOGIN_ENABLED=true 双条件。"""

    async def test_flag_off_blocks_even_in_dev(self, client: AsyncClient):
        settings.ENVIRONMENT = "development"
        settings.DEV_LOGIN_ENABLED = False
        try:
            r = await client.post("/api/v1/auth/dev-login")
            assert r.status_code == 404
        finally:
            settings.ENVIRONMENT = "test"

    async def test_flag_on_in_dev_allows(self, client: AsyncClient):
        settings.ENVIRONMENT = "development"
        settings.DEV_LOGIN_ENABLED = True
        try:
            r = await client.post("/api/v1/auth/dev-login")
            assert r.status_code == 200
        finally:
            settings.ENVIRONMENT = "test"
            settings.DEV_LOGIN_ENABLED = False


class TestDocsToggle:
    def test_docs_disabled_in_production(self):
        from app.config import docs_url
        settings.ENVIRONMENT = "production"
        try:
            assert docs_url() is None
        finally:
            settings.ENVIRONMENT = "test"

    def test_docs_enabled_in_dev(self):
        from app.config import docs_url
        settings.ENVIRONMENT = "development"
        try:
            assert docs_url() == "/docs"
        finally:
            settings.ENVIRONMENT = "test"


class TestSecurityHeaders:
    async def test_headers_on_health(self, client: AsyncClient):
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"


class TestCorsAllowlist:
    async def test_allowed_origin_echoed(self, client: AsyncClient):
        r = await client.get("/health", headers={"Origin": "http://localhost:5173"})
        assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"

    async def test_unknown_origin_gets_no_acao(self, client: AsyncClient):
        r = await client.get("/health", headers={"Origin": "https://evil.example.com"})
        assert "access-control-allow-origin" not in r.headers
