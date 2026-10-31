#!/usr/bin/env python3
"""学生端走查共享静态服务。

解决两件事：

1. **消除重复**：`frontend/scripts/` 下 7 个脚本原本各抄一份
   `SilentHandler` / `QuietHandler`（同一段代码抄了 7 遍，违反三次法则），
   统一收口到本模块，改一处即全部生效。
2. **消除偶发 ERR_CONNECTION_CLOSED**：Python 的
   `socketserver.TCPServer.request_queue_size` 默认只有 5。页面并发加载
   十几个资源（JS 分块、CSS、字体、图标）时 listen 队列容易被打满，
   浏览器侧表现为「Failed to load resource: net::ERR_CONNECTION_CLOSED」，
   走查会把它当成真实控制台错误而误判失败。这里把 backlog 提到 128，
   并容忍客户端提前断开（导航切页时在途请求被中断是正常现象）。

H5 走 hash 路由，静态服务不需要 SPA 回退 —— 这与管理台的
`admin-frontend/scripts/walkthrough_server.py` 不同。
"""

import http.server
import socket
import threading

# listen 队列深度：远大于浏览器单页并发请求数，避免队列打满导致连接被重置
REQUEST_QUEUE_SIZE = 128


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    """静态服务：静默日志 + 容忍客户端提前断开。"""

    dist_dir = ''

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=self.dist_dir, **kwargs)

    def copyfile(self, source, outputfile):
        # 浏览器切页/关闭时在途请求被中断，不要把异常抛到控制台
        try:
            super().copyfile(source, outputfile)
        except (ConnectionResetError, BrokenPipeError):
            pass

    def log_message(self, fmt, *args):
        pass


class WalkthroughServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = REQUEST_QUEUE_SIZE


def create_server(dist_dir):
    """启动共享静态服务，返回 (httpd, base_url)。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()

    handler = type('BoundQuietHandler', (QuietHandler,), {'dist_dir': dist_dir})
    httpd = WalkthroughServer(('127.0.0.1', port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f'http://127.0.0.1:{port}'
