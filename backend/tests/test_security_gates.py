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

    def test_production_strong_secret_passes(self, monkeypatch):
        monkeypatch.setattr(settings, "ZHENGFANG_BASE_URL", "")
        monkeypatch.setattr(settings, "ZHENGFANG_TEST_PASSWORD", "")
        monkeypatch.setattr(settings, "DEV_LOGIN_ENABLED", False)
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

@pytest.mark.parametrize('field,value', [
    ('JWT_SECRET', 'CHANGE_ME_INDEPENDENT_RANDOM_SECRET_AT_LEAST_32_CHARACTERS'),
    ('JWT_SECRET', 'REPLACE_WITH_RANDOM_PRODUCTION_JWT_SECRET'),
    ('VERIFICATION_FINGERPRINT_KEY', 'CHANGE_ME_INDEPENDENT_FINGERPRINT_SECRET_32_CHARS'),
])
def test_long_production_example_keys_are_rejected(monkeypatch, field, value):
    from app.config import validate_security_config
    configured = {
        'ENVIRONMENT': 'production', 'JWT_SECRET': 'j' * 48,
        'DATABASE_URL': 'postgresql+asyncpg://u:longrandom@db:5432/ey_wall',
        'REDIS_URL': 'redis://:longrandom@redis:6379/0',
        'CORS_ORIGINS': 'https://campus.example.edu.cn',
        'DEV_LOGIN_ENABLED': False, 'MODERATION_FAIL_OPEN': False,
        'ZHENGFANG_BASE_URL': '', 'ZHENGFANG_TEST_PASSWORD': '',
        'STUDENT_VERIFICATION_ENABLED': True,
        'VERIFICATION_FINGERPRINT_KEY': 'f' * 48,
        'VERIFICATION_FINGERPRINT_PREVIOUS_KEYS': '{}',
        'VERIFICATION_STORAGE_PROVIDER': 'cos',
        'VERIFICATION_COS_BUCKET': 'private-evidence', 'COS_BUCKET': 'private-media',
        'COS_SECRET_ID': 'synthetic-id', 'COS_SECRET_KEY': 'synthetic-key',
    }
    for name, setting in configured.items():
        monkeypatch.setattr(settings, name, setting)
    monkeypatch.setattr(settings, field, value)
    with pytest.raises(RuntimeError):
        validate_security_config()


def _production_verification_config(monkeypatch):
    """一套通过其它所有生产闸门的配置，只留学生证存储这一项可变。"""
    from app.config import settings as live
    configured = {
        'ENVIRONMENT': 'production', 'JWT_SECRET': 'j' * 48,
        'DATABASE_URL': 'postgresql+asyncpg://u:longrandom@db:5432/ey_wall',
        'REDIS_URL': 'redis://:longrandom@redis:6379/0',
        'CORS_ORIGINS': 'https://campus.example.edu.cn',
        'DEV_LOGIN_ENABLED': False, 'MODERATION_FAIL_OPEN': False,
        'ZHENGFANG_BASE_URL': '', 'ZHENGFANG_TEST_PASSWORD': '',
        'STUDENT_VERIFICATION_ENABLED': True,
        'VERIFICATION_FINGERPRINT_KEY': 'f' * 48,
        'VERIFICATION_FINGERPRINT_PREVIOUS_KEYS': '{}',
        'VERIFICATION_STORAGE_PROVIDER': 'local',
        'VERIFICATION_COS_BUCKET': '', 'COS_BUCKET': '',
        'COS_SECRET_ID': '', 'COS_SECRET_KEY': '',
        'VERIFICATION_ALLOW_LOCAL_IN_PRODUCTION': False,
    }
    for name, value in configured.items():
        monkeypatch.setattr(live, name, value)
    return live


def test_production_rejects_local_student_verification_storage(monkeypatch):
    """生产环境默认必须用独立私有 COS 桶，local 存储一律拒绝。"""
    from app.config import validate_security_config
    _production_verification_config(monkeypatch)
    with pytest.raises(RuntimeError, match="独立私有 COS 桶"):
        validate_security_config()


def test_production_allows_local_only_with_explicit_escape_hatch(monkeypatch):
    """显式打开逃生开关后，local 存储才被接受 —— 且仅限这一项放宽。"""
    from app.config import validate_security_config
    live = _production_verification_config(monkeypatch)
    monkeypatch.setattr(live, "VERIFICATION_ALLOW_LOCAL_IN_PRODUCTION", True)
    # 其它生产闸门不放宽：占位符密钥仍然必须被拒。
    monkeypatch.setattr(live, "JWT_SECRET", 'CHANGE_ME_INDEPENDENT_RANDOM_SECRET_AT_LEAST_32_CHARACTERS')
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        validate_security_config()


def test_verification_storage_layer_refuses_local_in_production(monkeypatch):
    """存储层自身也要拦住 local —— 绕过配置校验直接构造存储对象同样不行。"""
    from app.utils.verification_storage import VerificationStorage
    live = _production_verification_config(monkeypatch)
    monkeypatch.setattr(live, "STATIC_BASE_DIR", '/tmp/sw-public-static')
    monkeypatch.setattr(live, "VERIFICATION_PRIVATE_DIR", '/tmp/sw-private-verifications')
    with pytest.raises(RuntimeError, match="独立私有 COS 桶"):
        VerificationStorage()


def test_verification_storage_layer_allows_local_with_escape_hatch(monkeypatch):
    """逃生开关打开时，存储层允许 local，且认证照片目录不得落在公共静态目录里。"""
    from app.utils.verification_storage import VerificationStorage
    live = _production_verification_config(monkeypatch)
    monkeypatch.setattr(live, "VERIFICATION_ALLOW_LOCAL_IN_PRODUCTION", True)
    monkeypatch.setattr(live, "DEPLOY_ENVIRONMENT", 'staging')
    monkeypatch.setattr(live, "STATIC_BASE_DIR", '/tmp/sw-public-static')
    monkeypatch.setattr(live, "VERIFICATION_PRIVATE_DIR", '/tmp/sw-private-verifications')
    assert VerificationStorage().provider == 'local'

    monkeypatch.setattr(live, "VERIFICATION_PRIVATE_DIR", '/tmp/sw-public-static/proofs')
    with pytest.raises(RuntimeError, match="不得位于公共静态目录"):
        VerificationStorage()


def test_verification_escape_hatch_requires_staging(monkeypatch):
    """真生产部署即使误填了逃生开关也必须被拦住。"""
    from app.config import validate_security_config
    live = _production_verification_config(monkeypatch)
    monkeypatch.setattr(live, "VERIFICATION_ALLOW_LOCAL_IN_PRODUCTION", True)
    monkeypatch.setattr(live, "DEPLOY_ENVIRONMENT", 'production')
    with pytest.raises(RuntimeError, match="内测放宽开关"):
        validate_security_config()


def test_production_rejects_guest_and_auto_approve_switches(monkeypatch):
    """真生产部署不得开启 guest 交互或审核自动通过。"""
    from app.config import validate_security_config
    live = _production_verification_config(monkeypatch)
    monkeypatch.setattr(live, "DEPLOY_ENVIRONMENT", 'production')
    monkeypatch.setattr(live, "ALLOW_GUEST_INTERACTION", True)
    with pytest.raises(RuntimeError, match="ALLOW_GUEST_INTERACTION"):
        validate_security_config()

    monkeypatch.setattr(live, "ALLOW_GUEST_INTERACTION", False)
    monkeypatch.setattr(live, "AUTO_APPROVE_MODERATION", True)
    with pytest.raises(RuntimeError, match="AUTO_APPROVE_MODERATION"):
        validate_security_config()


def test_staging_allows_relaxed_switches(monkeypatch):
    """staging 部署可以同时开启全部内测放宽开关。"""
    from app.config import validate_security_config
    live = _production_verification_config(monkeypatch)
    monkeypatch.setattr(live, "DEPLOY_ENVIRONMENT", 'staging')
    monkeypatch.setattr(live, "ALLOW_GUEST_INTERACTION", True)
    monkeypatch.setattr(live, "AUTO_APPROVE_MODERATION", True)
    monkeypatch.setattr(live, "VERIFICATION_ALLOW_LOCAL_IN_PRODUCTION", True)
    validate_security_config()