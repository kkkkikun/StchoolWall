#!/usr/bin/env python3
"""电脑端走查共享静态服务。

两件事：

1. 走查脚本共用一份静态服务，不再各抄一份 handler（管理台与学生端都已收口）。
2. 兼容生产部署形态：电脑端按 `vite build --base=/pc/` 出制品，nginx 也以
   `location /pc/` 提供（deploy/nginx.schoolwall.conf），路由基址取
   `createWebHistory(import.meta.env.BASE_URL)`。走查若按根路径加载，静态资源会 404、
   页面直接白屏 —— 必须按同一前缀访问（管理台曾因前缀不匹配导致 34 个场景全挂）。

部署前缀由环境变量 `DESKTOP_BASE_PREFIX` 指定（默认 `/pc`）。
"""

import http.server
import os
import socket
import threading

BASE_PREFIX = os.environ.get('DESKTOP_BASE_PREFIX', '/pc').rstrip('/')


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
        if clean and not os.path.exists(full):
            # 带扩展名的缺失资源按 404 处理：把 index.html 当成 .js 返回会让浏览器报解析错误，
            # 走查会把它当成真实缺陷。其余路径回退到 index.html，交给前端路由。
            if os.path.splitext(clean)[1] or clean.startswith('api/'):
                self.send_error(404)
                return
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


def server_origin(base_url):
    """静态服务所在主机名（host:port），用于判定请求是否跨域。"""
    return base_url.split('//', 1)[-1].split('/', 1)[0]
