"""
正方教务系统真实链路 E2E 测试

需要配置以下 .env 变量才会执行（否则自动跳过）：
  ZHENGFANG_TEST_STUDENT_ID=你的学号
  ZHENGFANG_TEST_PASSWORD=你的密码
  ZHENGFANG_BASE_URL=http://jwxt.oit.edu.cn:40608/jwglxt

运行方式: pytest tests/test_zhengfang_e2e.py -v -s
"""

import pytest

from app.config import settings
from app.utils.zhengfang import verify_student

HAS_CREDENTIALS = bool(settings.ZHENGFANG_TEST_STUDENT_ID and settings.ZHENGFANG_TEST_PASSWORD)

pytestmark = pytest.mark.skipif(
    not HAS_CREDENTIALS,
    reason="需要在 .env 中配置 ZHENGFANG_TEST_STUDENT_ID 和 ZHENGFANG_TEST_PASSWORD",
)


@pytest.mark.asyncio
async def test_real_login_success():
    """真实学号密码能成功登录教务系统并获取姓名"""
    result = await verify_student(
        settings.ZHENGFANG_TEST_STUDENT_ID,
        settings.ZHENGFANG_TEST_PASSWORD,
        settings.ZHENGFANG_BASE_URL,
    )

    assert result["status"] == "success", f"登录失败: {result.get('msg')}"
    assert result.get("real_name"), "登录成功但未获取到 real_name"
    assert len(result["real_name"]) >= 2, f"姓名格式异常: {result['real_name']}"
    print(f"\n认证成功: 学号={settings.ZHENGFANG_TEST_STUDENT_ID}, 姓名={result['real_name']}")


@pytest.mark.asyncio
async def test_real_login_wrong_password():
    """错误密码必须返回失败"""
    result = await verify_student(
        settings.ZHENGFANG_TEST_STUDENT_ID,
        "WRONG_PASSWORD_12345",
        settings.ZHENGFANG_BASE_URL,
    )

    assert result["status"] == "fail", f"错误密码竟然登录成功了: {result}"
    assert "失败" in result.get("msg", "")


@pytest.mark.asyncio
async def test_real_login_nonexistent_student():
    """不存在的学号必须返回失败"""
    result = await verify_student(
        "99999999999",
        "whatever",
        settings.ZHENGFANG_BASE_URL,
    )

    assert result["status"] == "fail"
