"""内部测试反馈通道的接口测试。"""
import io
import json

import pytest
from PIL import Image

from app.config import settings
from app.services.feedback_notify import build_payload, build_text
from tests.conftest import auth_header

pytestmark = pytest.mark.asyncio


def _png_bytes(color=(200, 60, 90)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 24), color).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def feedback_env(monkeypatch, tmp_path):
    """反馈截图写到临时目录，避免污染仓库；测试口令固定。"""
    monkeypatch.setattr(settings, "FEEDBACK_TEST_CODE", "test-pass-123")
    monkeypatch.setattr(settings, "FEEDBACK_WEBHOOK_URL", "")
    monkeypatch.setattr(settings, "FEEDBACK_PRIVATE_DIR", str(tmp_path / "private-feedback"))
    yield


async def test_login_user_can_submit_feedback(client, student_token):
    response = await client.post("/api/v1/feedback", headers=auth_header(student_token), json={
        "category": "bug", "severity": "high", "title": "信息流加载失败",
        "content": "刷新后白屏", "page_url": "http://64.188.23.179/pc/",
        "route": "/pc/", "viewport": "1440x900", "theme": "light", "app_version": "pc",
        "diagnostics": {"errors": [{"message": "boom"}]},
    })
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["title"] == "信息流加载失败"
    assert body["data"]["severity"] == "high"
    assert body["data"]["status"] == "open"
    assert body["data"]["upload_token"]
    # 提交者昵称取自登录账号，但绝不回传真名/学号。
    assert body["data"]["reporter_name"] == "学生_测试"
    assert "real_name" not in json.dumps(body, ensure_ascii=False)
    assert "student_id" not in json.dumps(body, ensure_ascii=False)


async def test_feedback_with_screenshot_is_stored_privately(client, student_token):
    created = await client.post("/api/v1/feedback", headers=auth_header(student_token), json={
        "category": "ui", "title": "按钮颜色不对", "content": "详情页按钮是默认蓝"})
    assert created.status_code == 200
    feedback_id = created.json()["data"]["id"]

    uploaded = await client.post(f"/api/v1/feedback/{feedback_id}/screenshot",
        headers=auth_header(student_token),
        files={"file": ("shot.png", _png_bytes(), "image/png")})
    assert uploaded.status_code == 200
    assert uploaded.json()["data"]["screenshot_count"] == 1


async def test_screenshot_upload_requires_ownership_or_token(client, student_token, guest_token):
    created = await client.post("/api/v1/feedback", headers=auth_header(student_token), json={
        "category": "ui", "title": "别人也能传图吗", "content": "x"})
    feedback_id = created.json()["data"]["id"]

    # 另一个登录用户没有上传令牌，不能往别人的反馈里塞图。
    denied = await client.post(f"/api/v1/feedback/{feedback_id}/screenshot",
        headers=auth_header(guest_token),
        files={"file": ("shot.png", _png_bytes(), "image/png")})
    assert denied.status_code == 403

    allowed = await client.post(f"/api/v1/feedback/{feedback_id}/screenshot",
        files={"file": ("shot.png", _png_bytes(), "image/png")},
        data={"upload_token": created.json()["data"]["upload_token"]})
    assert allowed.status_code == 200


async def test_anonymous_submit_requires_test_code(client):
    response = await client.post("/api/v1/feedback", json={
        "category": "bug", "title": "匿名反馈", "content": "没有口令"})
    assert response.status_code == 403
    assert "口令" in response.json()["detail"]


async def test_anonymous_submit_with_wrong_code_is_rejected(client):
    response = await client.post("/api/v1/feedback", json={
        "category": "bug", "title": "匿名反馈", "content": "口令错误", "test_code": "wrong"})
    assert response.status_code == 403


async def test_anonymous_submit_with_correct_code_succeeds(client):
    response = await client.post("/api/v1/feedback", json={
        "category": "feature", "title": "想要暗黑模式", "content": "希望有暗色主题",
        "test_code": "test-pass-123", "reporter_name": "测试员小王"})
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["reporter_name"] == "测试员小王"
    assert body["id"] > 0
    assert body["upload_token"]


async def test_anonymous_submit_uploads_screenshot_with_token(client):
    created = await client.post("/api/v1/feedback", json={
        "category": "bug", "title": "匿名带图", "content": "x", "test_code": "test-pass-123"})
    feedback_id = created.json()["data"]["id"]
    uploaded = await client.post(f"/api/v1/feedback/{feedback_id}/screenshot",
        files={"file": ("shot.png", _png_bytes(), "image/png")},
        data={"upload_token": created.json()["data"]["upload_token"]})
    assert uploaded.status_code == 200


async def test_invalid_category_is_rejected(client, student_token):
    response = await client.post("/api/v1/feedback", headers=auth_header(student_token), json={
        "category": "unknown", "title": "x", "content": "y"})
    assert response.status_code == 422


async def test_blank_title_is_rejected(client, student_token):
    response = await client.post("/api/v1/feedback", headers=auth_header(student_token), json={
        "category": "bug", "title": "   ", "content": "y"})
    assert response.status_code == 400


async def test_too_many_screenshots_are_rejected(client, student_token):
    created = await client.post("/api/v1/feedback", headers=auth_header(student_token), json={
        "category": "bug", "title": "截图太多", "content": "x"})
    feedback_id = created.json()["data"]["id"]
    for index in range(5):
        ok = await client.post(f"/api/v1/feedback/{feedback_id}/screenshot",
            headers=auth_header(student_token),
            files={"file": (f"s{index}.png", _png_bytes((index * 10, 0, 0)), "image/png")})
        assert ok.status_code == 200
    overflow = await client.post(f"/api/v1/feedback/{feedback_id}/screenshot",
        headers=auth_header(student_token),
        files={"file": ("s5.png", _png_bytes(), "image/png")})
    assert overflow.status_code == 400
    assert "截图" in overflow.json()["detail"]


async def test_admin_can_list_detail_and_update_feedback(client, student_token,
                                                         console_headers):
    created = await client.post("/api/v1/feedback", headers=auth_header(student_token), json={
        "category": "bug", "severity": "high", "title": "发布失败", "content": "发帖报 500",
        "diagnostics": {"errors": [{"message": "500 Internal"}]}})
    feedback_id = created.json()["data"]["id"]

    listing = await client.get("/api/v1/admin/feedback", headers=console_headers)
    assert listing.status_code == 200
    assert listing.json()["data"]["total"] == 1
    assert "upload_token" not in json.dumps(listing.json(), ensure_ascii=False)

    stats = await client.get("/api/v1/admin/feedback/stats", headers=console_headers)
    assert stats.json()["data"]["open"] == 1

    detail = await client.get(f"/api/v1/admin/feedback/{feedback_id}", headers=console_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["diagnostics"]["errors"][0]["message"] == "500 Internal"

    updated = await client.put(f"/api/v1/admin/feedback/{feedback_id}", headers=console_headers,
        data={"status": "resolved", "note": "已修复"})
    assert updated.status_code == 200
    assert updated.json()["data"]["status"] == "resolved"
    assert updated.json()["data"]["note"] == "已修复"


async def test_admin_screenshot_endpoint_requires_auth(client, student_token):
    created = await client.post("/api/v1/feedback", headers=auth_header(student_token), json={
        "category": "ui", "title": "样式错乱", "content": "截图见附件"})
    feedback_id = created.json()["data"]["id"]
    await client.post(f"/api/v1/feedback/{feedback_id}/screenshot",
        headers=auth_header(student_token),
        files={"file": ("shot.png", _png_bytes(), "image/png")})
    anonymous = await client.get(f"/api/v1/admin/feedback/{feedback_id}/screenshot/0")
    assert anonymous.status_code == 401


async def test_admin_can_read_screenshot(client, student_token, console_headers):
    created = await client.post("/api/v1/feedback", headers=auth_header(student_token), json={
        "category": "ui", "title": "样式错乱", "content": "截图见附件"})
    feedback_id = created.json()["data"]["id"]
    await client.post(f"/api/v1/feedback/{feedback_id}/screenshot",
        headers=auth_header(student_token),
        files={"file": ("shot.png", _png_bytes(), "image/png")})
    shot = await client.get(f"/api/v1/admin/feedback/{feedback_id}/screenshot/0",
                            headers=console_headers)
    assert shot.status_code == 200
    assert shot.headers["content-type"].startswith("image/")
    assert len(shot.content) > 0


async def test_my_feedback_lists_only_own_submissions(client, student_token, guest_token):
    await client.post("/api/v1/feedback", headers=auth_header(student_token),
        json={"category": "bug", "title": "我的问题", "content": "x"})
    mine = await client.get("/api/v1/feedback/mine", headers=auth_header(student_token))
    assert mine.status_code == 200
    assert len(mine.json()["data"]["items"]) == 1

    others = await client.get("/api/v1/feedback/mine", headers=auth_header(guest_token))
    assert others.json()["data"]["items"] == []


async def test_webhook_payload_formats():
    from app.models.feedback import Feedback

    row = Feedback(id=7, category="bug", severity="high", title="标题", content="内容",
                   reporter_name="测试员", route="/pc/", viewport="1440x900",
                   diagnostics={"errors": [{"message": "boom"}]}, screenshots=[{"path": "x"}])
    text = build_text(row)
    assert "标题" in text and "boom" in text

    generic = build_payload(row)
    assert generic["type"] == "feedback" and generic["id"] == 7
    assert generic["screenshot_count"] == 1

    settings.FEEDBACK_WEBHOOK_KIND = "feishu"
    assert build_payload(row)["msg_type"] == "text"

    settings.FEEDBACK_WEBHOOK_KIND = "wecom"
    assert "text" in build_payload(row)

    settings.FEEDBACK_WEBHOOK_KIND = "generic"
