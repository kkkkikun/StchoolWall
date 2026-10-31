"""腾讯内容安全与持久任务审核测试：门禁 / verdict 分流 / 重试降级 / 通知。"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

import app.utils.moderation as moderation_module
import app.services.moderation as service_module
from app.config import settings
from app.models.notification import Notification
from app.models.post import Post
from app.models.user import User
from app.utils.moderation import ModerationResult, check_images, check_text
from tests.conftest import TestSession, auth_header

pytestmark = pytest.mark.asyncio


def _result(verdict: str, reason: str | None = None) -> ModerationResult:
    return ModerationResult(verdict=verdict, reason=reason, trace_id="trace_x")


async def _seed_pending(user_id, content="待审内容", images=None) -> int:
    async with TestSession() as db:
        p = Post(user_id=user_id, post_type="general", content=content,
                 images=images or [], status=0)
        db.add(p)
        await db.commit()
        await db.refresh(p)
        return p.id


async def _get_post_status(pid: int) -> int:
    async with TestSession() as db:
        p = (await db.execute(select(Post).where(Post.id == pid))).scalar_one()
        return p.status


class TestGating:
    async def test_not_configured_requires_manual_review(self, monkeypatch):
        """WECHAT_APP_ID 为空（开发环境）→ 直接 pass，不调微信。"""
        monkeypatch.setattr(settings, "TENCENT_SECRET_ID", "")
        result = await check_text("任何内容", "openid_x")
        assert result.verdict == "review"

        called = []
        async def _should_not_call(*a, **kw):
            called.append(1)
            raise AssertionError("不应调用微信 API")
        monkeypatch.setattr(moderation_module, "moderate", _should_not_call)
        result = await check_text("内容", "openid_x")
        assert result.verdict == "review"
        assert called == []

    async def test_images_empty_passes(self):
        result = await check_images([])
        assert result.verdict == "pass"


class TestVerdictFlow:
    """mock check_text/check_images 入口（service 依赖的绑定），绕过测试环境门禁。

    注意：check_post_moderation 内部用 app.database.async_session（主库），
    测试须替换为 TestSession，否则帖子查不到会静默跳过。
    """

    def _patch_service(self, monkeypatch):
        """把 service 内部的 async_session（主库工厂）替换为返回测试库上下文管理器的可调用。"""
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _ctx():
            async with TestSession() as s:
                yield s

        monkeypatch.setattr(service_module, "async_session", lambda: _ctx())

    def _patch_checks(self, monkeypatch, text_verdict: str, image_verdict: str = "pass"):
        async def _text(content, openid):
            return _result(text_verdict)
        async def _img(images):
            return _result(image_verdict)
        monkeypatch.setattr(service_module, "check_text", _text)
        monkeypatch.setattr(service_module, "check_images", _img)

    async def test_risky_rejected_and_notified(self, monkeypatch, student_user: User):
        """suggest=risky → status=-1 + 作者收到 moderation 通知。"""
        self._patch_service(monkeypatch)
        self._patch_checks(monkeypatch, "reject")

        pid = await _seed_pending(student_user.id, "违规内容")
        await service_module.check_post_moderation(pid)

        assert await _get_post_status(pid) == -1
        async with TestSession() as db:
            notifs = (await db.execute(
                select(Notification).where(Notification.user_id == student_user.id, Notification.type == "moderation")
            )).scalars().all()
            assert len(notifs) == 1
            assert notifs[0].post_id == pid

    async def test_review_stays_pending(self, monkeypatch, student_user: User):
        """suggest=review（机器不确定）→ 保持 0 进人工待审队列。"""
        self._patch_service(monkeypatch)
        self._patch_checks(monkeypatch, "review")

        pid = await _seed_pending(student_user.id, "存疑内容")
        with pytest.raises(service_module.ManualReviewRequired):
            await service_module.check_post_moderation(pid)
        assert await _get_post_status(pid) == 0

    async def test_pass_approved(self, monkeypatch, student_user: User):
        """suggest=pass → status=1。"""
        self._patch_service(monkeypatch)
        self._patch_checks(monkeypatch, "pass")

        pid = await _seed_pending(student_user.id, "正常内容")
        await service_module.check_post_moderation(pid)
        assert await _get_post_status(pid) == 1

    async def test_image_reject_dominates(self, monkeypatch, student_user: User):
        """图片 reject 覆盖文本 pass（取最严）。"""
        self._patch_service(monkeypatch)
        self._patch_checks(monkeypatch, "pass", "reject")

        pid = await _seed_pending(student_user.id, "文本正常图违规", images=["http://x/bad.jpg"])
        await service_module.check_post_moderation(pid)
        assert await _get_post_status(pid) == -1

    async def test_idempotent_only_pending(self, monkeypatch, student_user: User):
        """status!=0 的帖子直接跳过（幂等，防重复处理）。"""
        self._patch_service(monkeypatch)
        calls = []
        async def _text(content, openid):
            calls.append(content)
            return _result("pass")
        async def _img(images):
            return _result("pass")
        monkeypatch.setattr(service_module, "check_text", _text)
        monkeypatch.setattr(service_module, "check_images", _img)

        pid = await _seed_pending(student_user.id, "已处理")
        async with TestSession() as db:
            p = (await db.execute(select(Post).where(Post.id == pid))).scalar_one()
            p.status = 1
            await db.commit()

        await service_module.check_post_moderation(pid)
        assert calls == []  # 没有重新审核


class TestFailOpen:
    def _patch_service(self, monkeypatch):
        """把 service 内部的 async_session（主库工厂）替换为返回测试库上下文管理器的可调用。"""
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def _ctx():
            async with TestSession() as s:
                yield s

        monkeypatch.setattr(service_module, "async_session", lambda: _ctx())

    async def test_deprecated_fail_open_flag_does_not_bypass_review(self, monkeypatch, student_user: User):
        """旧配置也不能令审核故障的内容公开，交给持久任务重试。"""
        self._patch_service(monkeypatch)
        monkeypatch.setattr(settings, "MODERATION_FAIL_OPEN", True)

        async def _error(content, openid):
            return _result("error")
        async def _img_ok(images):
            return _result("pass")
        monkeypatch.setattr(service_module, "check_text", _error)
        monkeypatch.setattr(service_module, "check_images", _img_ok)

        pid = await _seed_pending(student_user.id, "网络故障时发布")
        with pytest.raises(service_module.ModerationRetry):
            await service_module.check_post_moderation(pid)
        assert await _get_post_status(pid) == 0

    async def test_error_fail_open_false(self, monkeypatch, student_user: User):
        """FAIL_OPEN=False → 保持 0 等人工。"""
        self._patch_service(monkeypatch)
        monkeypatch.setattr(settings, "MODERATION_FAIL_OPEN", False)

        async def _error(content, openid):
            return _result("error")
        async def _img_ok(images):
            return _result("pass")
        monkeypatch.setattr(service_module, "check_text", _error)
        monkeypatch.setattr(service_module, "check_images", _img_ok)

        pid = await _seed_pending(student_user.id, "网络故障时发布2")
        with pytest.raises(service_module.ModerationRetry):
            await service_module.check_post_moderation(pid)
        assert await _get_post_status(pid) == 0


class TestImageSeverities:
    async def test_multi_images_take_strictest(self):
        """多图取最严：reject > review > error > pass。"""
        severities = {"a.jpg": "pass", "b.jpg": "review", "c.jpg": "reject"}

        async def _img_by_url(images):
            verdicts = [severities[img] for img in images]
            worst = "reject" if "reject" in verdicts else ("review" if "review" in verdicts else "pass")
            return _result(worst)

        # 直接测聚合语义（绕过微信门禁：空 APP_ID 时 check_images 直接 pass，
        # 所以这里测 service 层的聚合函数 _strictest）
        from app.utils.moderation import _strictest
        assert _strictest([_result("pass"), _result("review")]).verdict == "review"
        assert _strictest([_result("review"), _result("reject")]).verdict == "reject"
        assert _strictest([_result("pass")]).verdict == "pass"
        assert _strictest([_result("error"), _result("pass")]).verdict == "error"
