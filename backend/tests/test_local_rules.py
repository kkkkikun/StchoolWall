"""本地敏感词规则测试：纯匹配器 + 管线接入（rule/freq 判定、记录持久化、重试不重复写）。

管线测试沿用 test_wechat_moderation.py 的 seam：patch service_module.async_session → TestSession。
"""
import pytest
from sqlalchemy import select

import app.services.moderation as service_module
from app.config import settings
from app.models.moderation_record import ModerationRecord
from app.models.notification import Notification
from app.models.post import Post
from app.models.sensitive_word import SensitiveWord
from app.models.user import User
from app.utils.local_rules import check_text_local, normalize_text
from app.utils.moderation import ModerationResult
from tests.conftest import TestSession

pytestmark = pytest.mark.asyncio


# ---- helpers ----

async def _seed_word(word: str, level: str = "hard") -> None:
    async with TestSession() as db:
        db.add(SensitiveWord(word=word, level=level))
        await db.commit()


async def _seed_post(user_id, content="待审内容", status=1) -> int:
    async with TestSession() as db:
        p = Post(user_id=user_id, post_type="general", content=content, images=[], status=status)
        db.add(p)
        await db.commit()
        await db.refresh(p)
        return p.id


async def _get_post_status(pid: int) -> int:
    async with TestSession() as db:
        p = (await db.execute(select(Post).where(Post.id == pid))).scalar_one()
        return p.status


async def _records(pid: int) -> list[tuple[str, str, list | None, str | None, str | None]]:
    """(source, verdict, matched, reason, trace_id) 按写入顺序。"""
    async with TestSession() as db:
        rows = (await db.execute(
            select(ModerationRecord).where(ModerationRecord.post_id == pid).order_by(ModerationRecord.id)
        )).scalars().all()
        return [(r.source, r.verdict, r.matched, r.reason, r.trace_id) for r in rows]


def _patch_service(monkeypatch):
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _ctx():
        async with TestSession() as s:
            yield s

    monkeypatch.setattr(service_module, "async_session", lambda: _ctx())


def _patch_wechat(monkeypatch, text_verdict: str, image_verdict: str = "pass"):
    async def _text(content, openid):
        return ModerationResult(verdict=text_verdict, reason=f"wechat:{text_verdict}", trace_id="trace_x")
    async def _img(images):
        return ModerationResult(verdict=image_verdict)
    monkeypatch.setattr(service_module, "check_text", _text)
    monkeypatch.setattr(service_module, "check_images", _img)


def _patch_sleep(monkeypatch):
    async def _no_sleep(s):
        pass
    monkeypatch.setattr(service_module, "_backoff_sleep", _no_sleep)


# ---- 纯匹配器 ----

class TestLocalMatcher:

    async def test_hard_word_rejects(self):
        result, matched = check_text_local("急找人代考，价格好商量", [("代考", "hard")])
        assert result.verdict == "reject"
        assert "代考" in result.reason
        assert matched == ["代考"]

    async def test_gray_word_reviews(self):
        result, matched = check_text_local("你真是个垃圾人", [("垃圾人", "gray")])
        assert result.verdict == "review"
        assert matched == ["垃圾人"]

    async def test_clean_content_passes(self):
        result, matched = check_text_local("今天食堂出了新菜，好吃", [("代考", "hard")])
        assert result.verdict == "pass"
        assert matched == []

    async def test_empty_words_passes(self):
        result, matched = check_text_local("任何内容", [])
        assert result.verdict == "pass"
        assert matched == []

    async def test_empty_content_passes(self):
        result, matched = check_text_local("", [("代考", "hard")])
        assert result.verdict == "pass"

    async def test_hard_dominates_gray(self):
        result, matched = check_text_local("找人代考，你个垃圾人", [("代考", "hard"), ("垃圾人", "gray")])
        assert result.verdict == "reject"
        assert "代考" in result.reason

    async def test_evasion_fullwidth_and_whitespace(self):
        """全角字符 + 插空格的变体仍命中（NFKC + 去空白归一化）。"""
        result, _ = check_text_local("急找ｄａｉ　考　枪手", [("代考", "hard"), ("枪手", "hard")])
        assert result.verdict == "reject"

    async def test_normalize_text(self):
        assert normalize_text("Ａｂｃ１２３") == "abc123"
        assert normalize_text("代　考") == "代考"          # 全角空格
        assert normalize_text("代​考") == "代考"       # 零宽字符
        assert normalize_text("A B\tC\n") == "abc"
        assert normalize_text("") == ""


# ---- 管线接入 ----

class TestLocalRulesFlow:

    async def test_local_hard_rejects_and_records(self, monkeypatch, student_user: User):
        """硬词命中 → status=-1 + 通知 + 恰好 1 条 rule/reject 记录（含 matched），无 wechat 行。"""
        _patch_service(monkeypatch)
        await _seed_word("代考", "hard")

        pid = await _seed_post(student_user.id, "急找代考枪手", status=0)
        await service_module.check_post_moderation(pid)

        assert await _get_post_status(pid) == -1
        async with TestSession() as db:
            notifs = (await db.execute(
                select(Notification).where(Notification.user_id == student_user.id, Notification.type == "moderation")
            )).scalars().all()
            assert len(notifs) == 1
            assert notifs[0].post_id == pid

        rows = await _records(pid)
        assert len(rows) == 1
        source, verdict, matched, reason, _ = rows[0]
        assert source == "rule"
        assert verdict == "reject"
        assert "代考" in (matched or [])
        assert "代考" in (reason or "")

    async def test_local_gray_stays_pending_with_record(self, monkeypatch, student_user: User):
        """灰词命中 → 保持待审，且 rule/review 记录已落库（review 分支必须 commit）。"""
        _patch_service(monkeypatch)
        await _seed_word("垃圾人", "gray")

        pid = await _seed_post(student_user.id, "你真是个垃圾人", status=0)
        await service_module.check_post_moderation(pid)

        assert await _get_post_status(pid) == 0
        rows = await _records(pid)
        assert len(rows) == 1
        assert rows[0][0] == "rule"
        assert rows[0][1] == "review"
        assert "垃圾人" in (rows[0][2] or [])

    async def test_clean_post_passes_with_pass_record(self, monkeypatch, student_user: User):
        """干净帖 → status=1 + rule/pass 记录。"""
        _patch_service(monkeypatch)
        await _seed_word("代考", "hard")

        pid = await _seed_post(student_user.id, "正常的学习交流帖", status=0)
        await service_module.check_post_moderation(pid)

        assert await _get_post_status(pid) == 1
        rows = await _records(pid)
        assert len(rows) == 1
        assert rows[0][0] == "rule"
        assert rows[0][1] == "pass"

    async def test_local_reject_dominates_wechat_pass(self, monkeypatch, student_user: User):
        """本地硬词 reject 压过微信 pass（且跳过微信调用省配额）。"""
        _patch_service(monkeypatch)
        wechat_calls = []
        async def _text(content, openid):
            wechat_calls.append(content)
            return ModerationResult(verdict="pass", trace_id="trace_x")
        async def _img(images):
            return ModerationResult(verdict="pass")
        monkeypatch.setattr(service_module, "check_text", _text)
        monkeypatch.setattr(service_module, "check_images", _img)
        await _seed_word("代考", "hard")

        pid = await _seed_post(student_user.id, "找人代考", status=0)
        await service_module.check_post_moderation(pid)

        assert await _get_post_status(pid) == -1
        assert wechat_calls == []  # 本地已 reject，微信未调用

    async def test_wechat_record_written_when_configured(self, monkeypatch, student_user: User):
        """_is_configured=True 时补写 wechat 行（rule pass + wechat reject 两条）。"""
        _patch_service(monkeypatch)
        _patch_wechat(monkeypatch, "reject")
        monkeypatch.setattr(service_module, "_is_configured", lambda: True)

        pid = await _seed_post(student_user.id, "微信判定违规的内容", status=0)
        await service_module.check_post_moderation(pid)

        assert await _get_post_status(pid) == -1
        rows = await _records(pid)
        assert [(r[0], r[1]) for r in rows] == [("rule", "pass"), ("wechat", "reject")]
        assert rows[1][4] == "trace_x"

    async def test_error_retry_single_record(self, monkeypatch, student_user: User):
        """微信 error 重试 3 次耗尽 → 仅 1 条 wechat/error 记录（防循环内重复写）。"""
        _patch_service(monkeypatch)
        _patch_wechat(monkeypatch, "error")
        _patch_sleep(monkeypatch)
        monkeypatch.setattr(service_module, "_is_configured", lambda: True)
        monkeypatch.setattr(settings, "MODERATION_FAIL_OPEN", False)

        pid = await _seed_post(student_user.id, "网络故障时发布", status=0)
        await service_module.check_post_moderation(pid)

        assert await _get_post_status(pid) == 0
        rows = await _records(pid)
        assert [(r[0], r[1]) for r in rows] == [("rule", "pass"), ("wechat", "error")]


class TestFrequencyGuard:

    async def test_frequency_triggers_review(self, monkeypatch, student_user: User):
        """10 分钟内第 3 帖 → 转人工（保持 0），rule 记录 reason 含"高频"。"""
        _patch_service(monkeypatch)
        await _seed_post(student_user.id, "第1帖", status=1)
        await _seed_post(student_user.id, "第2帖", status=1)

        pid = await _seed_post(student_user.id, "第3帖", status=0)
        await service_module.check_post_moderation(pid)

        assert await _get_post_status(pid) == 0
        rows = await _records(pid)
        assert rows[0][0] == "rule"
        assert rows[0][1] == "review"
        assert "高频" in (rows[0][3] or "")

    async def test_frequency_not_triggered(self, monkeypatch, student_user: User):
        """窗口内仅 1 帖 → 正常过审。"""
        _patch_service(monkeypatch)
        pid = await _seed_post(student_user.id, "唯一的帖子", status=0)
        await service_module.check_post_moderation(pid)
        assert await _get_post_status(pid) == 1
