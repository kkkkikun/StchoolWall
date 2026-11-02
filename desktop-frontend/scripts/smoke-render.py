#!/usr/bin/env python3
"""电脑端运行时冒烟：本地静态服务 + /api/ 转发 + Chromium 打开 /pc/。

断言：页面渲染出顶栏与信息流、控制台无 JS 异常、截图留档。
API 转发到真实后端，因此能验证读链路的真实联通情况。

用法: python3 desktop-frontend/scripts/smoke-render.py [--dist <目录>] [--port 8138] [--api http://127.0.0.1:8000]
"""
import argparse
import http.server
import json
import pathlib
import socketserver
import sys
import threading
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]


def make_handler(dist: pathlib.Path, api_base: str):
    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def translate_path(self, path: str) -> str:
            if path.startswith("/pc/"):
                path = path[len("/pc"):]
            return str(dist / path.lstrip("/"))

        def do_GET(self):
            if self.path.startswith("/api/"):
                return self.proxy("GET")
            return self.serve_static()

        def do_POST(self):
            if self.path.startswith("/api/"):
                return self.proxy("POST")
            self.send_error(405)

        def proxy(self, method: str):
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else None
            request = urllib.request.Request(
                api_base + self.path, data=body, method=method,
                headers={"Content-Type": self.headers.get("Content-Type", "application/json")},
            )
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    payload = response.read()
                    self.send_response(response.status)
                    self.send_header("Content-Type", response.headers.get("Content-Type", "application/json"))
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
            except urllib.error.HTTPError as error:
                payload = error.read()
                self.send_response(error.code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except Exception as error:  # 网络不可达时如实返回 502
                payload = json.dumps({"detail": str(error)}).encode()
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        def content_type(self, target: pathlib.Path) -> str:
            suffix = target.suffix.lower()
            return {
                ".html": "text/html; charset=utf-8",
                ".js": "text/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8",
                ".json": "application/json; charset=utf-8",
                ".svg": "image/svg+xml",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".webp": "image/webp",
                ".gif": "image/gif",
                ".woff2": "font/woff2",
                ".ttf": "font/ttf",
            }.get(suffix, "application/octet-stream")

        def serve_static(self):
            target = pathlib.Path(self.translate_path(self.path))
            if target.is_dir():
                target = target / "index.html"
            if not target.exists():
                self.send_error(404)
                return
            payload = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", self.content_type(target))
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", default=str(ROOT / "desktop-frontend" / "dist"))
    parser.add_argument("--port", type=int, default=8138)
    parser.add_argument("--api", default="http://64.188.23.179")
    parser.add_argument("--bind", default="127.0.0.1")
    args = parser.parse_args()

    dist = pathlib.Path(args.dist)
    if not (dist / "index.html").exists():
        print(f"找不到构建产物：{dist}", file=sys.stderr)
        return 2

    from playwright.sync_api import sync_playwright

    class ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        # 浏览器会并发请求，单线程会在并发连接上互锁
        daemon_threads = True
        allow_reuse_address = True

    httpd = ThreadedServer((args.bind, args.port), make_handler(dist, args.api))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    errors: list[str] = []
    base = f"http://{args.bind}:{args.port}/pc/"
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.on("console", lambda msg: errors.append(f"{msg.type}: {msg.text}") if msg.type == "error" else None)
            page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
            page.goto(base, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
            title = page.title()
            brand = page.locator(".sw-logo__text").inner_text() if page.locator(".sw-logo__text").count() else ""
            cards = page.locator(".sw-post").count()
            page.screenshot(path=str(ROOT / "desktop-frontend" / "smoke-render.png"), full_page=False)
            browser.close()
    finally:
        httpd.shutdown()

    print(f"标题：{title}")
    print(f"顶栏品牌：{brand}")
    print(f"信息流卡片数：{cards}")
    print(f"控制台错误 {len(errors)} 条")
    for item in errors[:8]:
        print("  -", item)
    if not brand:
        print("没渲染出顶栏品牌，骨架可能有问题")
        return 1
    if errors:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
