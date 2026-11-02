#!/usr/bin/env python3
"""电脑端反馈入口冒烟：打开 /pc/ → 点反馈按钮 → 断言弹窗关键控件齐全。

反馈弹窗是懒加载组件，只有真的点开才会加载，
所以这一段不能靠首屏断言覆盖，必须交互一次。

用法: python3 desktop-frontend/scripts/feedback-smoke.py [--dist <目录>] [--port 8141] [--api http://64.188.23.179]
"""
import argparse
import http.server
import importlib.util
import pathlib
import socketserver
import sys
import threading

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _load_smoke_handler():
    """复用 smoke-render.py 里的静态服务与接口转发（文件名带连字符，只能按路径加载）。"""
    path = ROOT / "desktop-frontend" / "scripts" / "smoke-render.py"
    spec = importlib.util.spec_from_file_location("smoke_render", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.make_handler


make_handler = _load_smoke_handler()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", default=str(ROOT / "desktop-frontend" / "dist"))
    parser.add_argument("--port", type=int, default=8141)
    parser.add_argument("--api", default="http://64.188.23.179")
    parser.add_argument("--bind", default="127.0.0.1")
    args = parser.parse_args()

    dist = pathlib.Path(args.dist)
    if not (dist / "index.html").exists():
        print(f"找不到构建产物：{dist}", file=sys.stderr)
        return 2

    from playwright.sync_api import sync_playwright

    class ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        daemon_threads = True
        allow_reuse_address = True

    httpd = ThreadedServer((args.bind, args.port), make_handler(dist, args.api))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    errors: list[str] = []
    base = f"http://{args.bind}:{args.port}/pc/"
    checks: list[tuple[str, bool]] = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.on("console", lambda msg: errors.append(f"{msg.type}: {msg.text}") if msg.type == "error" else None)
            page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
            page.goto(base, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(2500)

            trigger = page.locator(".sw-feedback-trigger")
            checks.append(("顶栏有反馈入口按钮", trigger.count() == 1))
            trigger.click()
            page.wait_for_selector(".el-dialog", timeout=15000)
            page.wait_for_timeout(1200)

            dialog = page.locator(".el-dialog")
            checks.append(("反馈弹窗已打开", dialog.count() >= 1))
            checks.append(("类型选择可用", page.locator(".el-dialog .el-radio-button").count() >= 4))
            checks.append(("标题输入框存在", page.locator(".el-dialog input").count() >= 1))
            checks.append(("描述输入框存在", page.locator(".el-dialog textarea").count() >= 1))
            checks.append(("截图上传控件存在", page.locator(".el-dialog .el-upload").count() >= 1))
            checks.append(("诊断信息开关存在", page.locator(".el-dialog .el-switch").count() >= 1))
            checks.append(("未登录时提示填写口令", page.locator(".el-dialog").inner_text().find("内部测试口令") >= 0))

            shot = ROOT / "desktop-frontend" / "feedback-smoke.png"
            page.screenshot(path=str(shot), full_page=False)
            browser.close()
    finally:
        httpd.shutdown()

    failed = 0
    for name, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        if not ok:
            failed += 1
    print(f"控制台错误 {len(errors)} 条")
    for item in errors[:8]:
        print("  -", item)
    if failed or errors:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
