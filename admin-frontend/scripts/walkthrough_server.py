#!/usr/bin/env python3
"""管理台走查共享静态服务。

解决两件事：

1. 11 套走查脚本原本各抄一份 `SPAHandler`（同一段代码抄了 11 遍，违反三次法则），
   统一收口到本模块，改一处即全部生效。
2. 兼容生产部署形态：nginx 以 `location /admin/` 提供管理台
   （deploy/nginx.schoolwall.conf），CI 也用 `vite build --base=/admin/` 出制品，
   路由基址取 `createWebHistory(import.meta.env.BASE_URL)`。
   走查若按根路径加载，静态资源会 404，页面直接白屏 —— 必须按同一前缀访问。

部署前缀由环境变量 `ADMIN_BASE_PREFIX` 指定（默认空 = 根路径部署）。
本地验证 /admin 形态：

    ADMIN_BASE_PREFIX=/admin python3 scripts/all-views-walkthrough.py
"""

import http.server
import os
import socket
import threading

BASE_PREFIX = os.environ.get('ADMIN_BASE_PREFIX', '').rstrip('/')


class SPAHandler(http.server.SimpleHTTPRequestHandler):
    """静态服务 + SPA 回退，并按 BASE_PREFIX 剥离部署前缀。"""

    dist_dir = ''

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=self.dist_dir, **kwargs)

    @staticmethod
    def _strip_prefix(path):
        if BASE_PREFIX and path.startswith(BASE_PREFIX + '/'):
            return path[len(BASE_PREFIX):]
        return path

    def do_GET(self):
        clean = self._strip_prefix(self.path.split('?')[0].split('#')[0]).lstrip('/')
        full = os.path.join(self.dist_dir, clean)
        if not (clean and os.path.exists(full) and not os.path.isdir(full)):
            self.path = '/index.html'
        return super().do_GET()

    def translate_path(self, path):
        path = path.split('?', 1)[0].split('#', 1)[0]
        return super().translate_path(self._strip_prefix(path))

    def copyfile(self, source, outputfile):
        # 浏览器提前断开时不要把异常抛到控制台
        try:
            super().copyfile(source, outputfile)
        except (ConnectionResetError, BrokenPipeError):
            pass

    def log_message(self, fmt, *args):
        pass


def create_server(dist_dir):
    """启动共享静态服务，返回 (httpd, base_url)。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()

    handler = type('BoundSPAHandler', (SPAHandler,), {'dist_dir': dist_dir})
    httpd = http.server.ThreadingHTTPServer(('127.0.0.1', port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f'http://127.0.0.1:{port}'


def route_url(base_url, path):
    """拼出带部署前缀的页面地址。"""
    if not path.startswith('/'):
        path = '/' + path
    return f'{base_url}{BASE_PREFIX}{path}'
