"""内测放宽开关的行为测试：guest 参与写操作、审核「需人工复核」自动降级。

这两个开关只在 DEPLOY_ENVIRONMENT=staging 时生效；真生产部署无法开启
（见 test_security_gates.py 的生产闸门测试）。
"""
import pytest
from httpx import AsyncClient

from app.config import settings
from app.models.user import User
from app.utils.moderation import ModerationResult, auto_approve_review
from tests.conftest import auth_header


class TestAutoApproveModeration:
    """审核自动通过：只降级 review，reject 不动。"""

    def test_review_becomes_pass_in_staging(self, monkeypatch):
        monkeypatch.setattr(settings, "AUTO_APPROVE_MODERATION", True)
        monkeypatch.setattr(settings, "DEPLOY_ENVIRONMENT", "staging")
        result = auto_approve_review(ModerationResult("review", reason="posting_frequency"))
        assert result.verdict == "pass"

    def test_reject_is_never_downgraded(self, monkeypatch):
        """命中敏感词被拒的内容仍然拒绝 —— 内容安全底线不因内测开关而放松。"""
        monkeypatch.setattr(settings, "AUTO_APPROVE_MODERATION", True)
        monkeypatch.setattr(settings, "DEPLOY_ENVIRONMENT", "staging")
        result = auto_approve_review(ModerationResult("reject", reason="sensitive_word"))
        assert result.verdict == "reject"

    def test_switch_off_keeps_review(self, monkeypatch):
        monkeypatch.setattr(settings, "AUTO_APPROVE_MODERATION", False)
        monkeypatch.setattr(settings, "DEPLOY_ENVIRONMENT", "staging")
        result = auto_approve_review(ModerationResult("review"))
        assert result.verdict == "review"

    def test_production_deployment_ignores_switch(self, monkeypatch):
        """真生产部署即使填了开关也不生效。"""
        monkeypatch.setattr(settings, "AUTO_APPROVE_MODERATION", True)
        monkeypatch.setattr(settings, "DEPLOY_ENVIRONMENT", "production")
        result = auto_approve_review(ModerationResult("review"))
        assert result.verdict == "review"


class TestGuestInteraction:
    """guest 参与写操作：仅在 staging 且开关打开时放行。"""

    @pytest.mark.asyncio
    async def test_guest_cannot_update_profile_by_default(
            self, client: AsyncClient, guest_token: str):
        """默认状态下 guest 改资料仍然是 403 —— 闸门默认不放宽。"""
        r = await client.put("/api/v1/user/profile",
                             headers=auth_header(guest_token),
                             json={"bio": "内测资料修改"})
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_guest_can_update_profile_when_enabled(
            self, client: AsyncClient, guest_token: str, monkeypatch):
        """开关打开且是 staging 时，guest 可以改资料。"""
        monkeypatch.setattr(settings, "ALLOW_GUEST_INTERACTION", True)
        monkeypatch.setattr(settings, "DEPLOY_ENVIRONMENT", "staging")
        r = await client.put("/api/v1/user/profile",
                             headers=auth_header(guest_token),
                             json={"bio": "内测资料修改"})
        # 只要不是 403 就说明角色闸门放行了（后续可能是审核相关的其它状态码）
        assert r.status_code != 403

    @pytest.mark.asyncio
    async def test_guest_still_blocked_in_production_deployment(
            self, client: AsyncClient, guest_token: str, monkeypatch):
        """真生产部署里 guest 改资料仍必须是 403。"""
        monkeypatch.setattr(settings, "ALLOW_GUEST_INTERACTION", True)
        monkeypatch.setattr(settings, "DEPLOY_ENVIRONMENT", "production")
        r = await client.put("/api/v1/user/profile",
                             headers=auth_header(guest_token),
                             json={"bio": "内测资料修改"})
        assert r.status_code == 403
