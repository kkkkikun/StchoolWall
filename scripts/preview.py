#!/usr/bin/env python3
"""
SchoolWall 本地预览服务（无需数据库）。

直接起一个静态服务器托管已构建产物，并对 /api/v1/** 返回与后端契约一致的 Mock 数据，
用于在没有 PostgreSQL/Redis 的机器上直接查看界面效果。

用法：
    python3 scripts/preview.py web      # 学生端 H5  -> http://127.0.0.1:5173
    python3 scripts/preview.py admin    # 管理后台   -> http://127.0.0.1:5174
    python3 scripts/preview.py web --port 6001

注意：这是**前端效果预览**，数据为本地 Mock，不代表后端已启动或接口已联调；
真实联调请起后端并改用 npm run dev:h5 / npm run dev。
"""

import argparse
import json
import os
import re
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- 通用夹具
USER_ID = '11111111-1111-4111-8111-111111111111'

PROFILE = {
    'id': USER_ID, 'nickname': '走查同学', 'avatar_url': None, 'banner_url': None,
    'bio': '计算机学院大三｜图书馆常驻｜偶尔发发呆', 'is_verified': True, 'school': '示例大学',
    'posts_count': 12, 'following_count': 34, 'followers_count': 56, 'is_following': False,
    'is_self': True,
}

AUTHOR = {'nickname': '走查同学', 'id': 'u-1', 'avatar_url': None, 'is_verified': True}


def make_post(i: int) -> dict:
    return {
        'id': i,
        'post_type': ['general', 'second_hand', 'lost_found'][i % 3],
        'category': ['广场', '二手', '失物'][i % 3],
        'content': f'第{i}条走查用帖子：用于验证信息流渲染与长文本换行表现，内容需要足够长以触发多行排版检查。',
        'images': [], 'images_count': 0, 'price': 99.0 if i % 3 == 1 else None,
        'status': 1, 'is_pinned': i == 2, 'is_featured': i == 3,
        'user': AUTHOR, 'author': AUTHOR,
        'like_count': i * 3, 'comment_count': i, 'view_count': 100 + i,
        'is_liked': False, 'is_favorited': False,
        'created_at': f'2026-10-{(i % 28) + 1:02d}T08:00:00Z',
    }


POSTS = [make_post(i) for i in range(1, 9)]

COMMENTS = [{
    'id': i, 'content': f'第{i}条走查用评论：验证评论渲染与回复层级。',
    'post_id': 1, 'user': AUTHOR,
    'created_at': f'2026-10-{(i % 28) + 1:02d}T08:00:00Z',
} for i in range(1, 5)]

PARTIES = [{
    'id': i, 'type': 'group', 'category': '学习', 'title': f'第{i}个组局',
    'content': '每晚七点图书馆三楼一起刷题，人满为止。', 'total': 6, 'joined_count': i,
    'status': 1, 'meet_time': '2026-10-25T19:00:00', 'location': '图书馆三楼',
    'user': {'nickname': '走查同学'}, 'organizer': {'nickname': '走查同学', 'id': 'u-1'},
    'is_joined': False, 'created_at': '2026-10-20T08:00:00Z',
} for i in range(1, 4)]

NOTIFICATIONS = [{
    'id': i, 'type': ['comment', 'like', 'announcement'][i % 3],
    'actor': {'nickname': '走查同学'}, 'post_id': i, 'comment_id': None, 'is_read': i % 2 == 0,
    'created_at': '2026-10-22T08:00:00Z',
    'payload': {'title': '公告标题', 'content': '公告正文，用于验证公告详情渲染。'},
} for i in range(1, 5)]

TAGS = [{'id': i, 'name': f'标签{i}'} for i in range(1, 4)]
HOT_USERS = [{'id': USER_ID, 'nickname': '走查同学', 'avatar_url': None, 'heat': 128}]

ADMIN_POSTS = [{
    'id': i, 'post_type': ['general', 'second_hand', 'lost_found'][i % 3],
    'category': ['广场', '二手', '失物'][i % 3],
    'content': f'第{i}条走查用帖子：用于验证管理端列表、筛选与状态徽标渲染。',
    'images': [], 'images_count': 0, 'price': 99.0 if i % 3 == 1 else None,
    'status': [1, 0, -1][i % 3], 'is_pinned': i == 2, 'is_featured': i == 3,
    'author': AUTHOR, 'like_count': i, 'comment_count': i % 5, 'view_count': 100 + i,
    'created_at': '2026-10-25T08:00:00Z',
} for i in range(1, 9)]

ADMIN_USERS = [{
    'id': f'u-{i}', 'username': f'user{i}', 'nickname': f'用户{i}', 'avatar_url': None,
    'role': 'student', 'status': 1, 'is_verified': i % 2 == 0,
    'post_count': i, 'comment_count': i, 'like_count': i,
    'created_at': '2026-10-25T08:00:00Z', 'last_login_at': '2026-10-25T08:00:00Z',
} for i in range(1, 7)]

ADMIN_REPORTS = [{
    'id': i, 'reason': '不友善言论', 'description': '举报说明，用于验证举报列表渲染。',
    'status': 'pending', 'reporter': AUTHOR, 'target_post_id': i,
    'created_at': '2026-10-25T08:00:00Z', 'handled_at': None,
} for i in range(1, 5)]

ADMIN_COMMENTS = [{
    'id': i, 'content': f'第{i}条走查用评论：验证评论管理与软删状态展示。',
    'post_id': i, 'post_content': '被评论的帖子标题', 'user': AUTHOR,
    'status': 1, 'created_at': '2026-10-25T08:00:00Z',
} for i in range(1, 5)]

ADMIN_PARTIES = [{
    'id': i, 'type': 'group', 'category': '学习', 'title': f'第{i}个组局',
    'content': '组局说明，用于验证组局管理列表。', 'total': 6, 'joined_count': i,
    'status': 1, 'meet_time': '2026-10-25T08:00:00Z', 'location': '图书馆',
    'organizer': {'nickname': '走查同学', 'id': 'u-1'}, 'created_at': '2026-10-25T08:00:00Z',
} for i in range(1, 4)]

ADMIN_BANNERS = [{
    'id': i, 'title': f'轮播位{i}', 'image_url': None, 'link_url': None,
    'sort': i, 'status': 1, 'start_at': '2026-10-25T08:00:00Z',
    'end_at': '2026-10-30T08:00:00Z', 'created_at': '2026-10-25T08:00:00Z',
} for i in range(1, 4)]

ADMIN_ANNOUNCEMENTS = [{
    'id': i, 'title': f'公告{i}', 'content': '公告正文内容，用于验证公告群发列表。',
    'status': 1, 'created_at': '2026-10-25T08:00:00Z', 'sent_count': i,
} for i in range(1, 4)]

ADMIN_LOGS = [{
    'id': i, 'admin_name': '走查管理员', 'action': 'post.status', 'target_type': 'post',
    'target_id': str(i), 'detail': '操作详情，用于验证日志列表渲染。',
    'ip': '127.0.0.1', 'created_at': '2026-10-25T08:00:00Z',
} for i in range(1, 5)]

ADMIN_SENSITIVE = [{'id': i, 'word': f'违禁词{i}', 'category': '其他', 'status': 1,
                     'created_at': '2026-10-25T08:00:00Z'} for i in range(1, 4)]

ADMIN_MOD_RECORDS = [{
    'id': i, 'source': 'rule', 'decision': 'pass', 'reason': '命中本地敏感词',
    'trace_id': f'trace-{i}', 'created_at': '2026-10-25T08:00:00Z',
} for i in range(1, 4)]

ADMIN_VERIFICATIONS = [{
    'id': f'v-{i}', 'user_id': 'u-1', 'username': f'user{i}', 'nickname': f'用户{i}',
    'school_id': 'demo', 'status': 'pending', 'consent_version': 'v1',
    'submitted_at': '2026-10-25T08:00:00Z', 'created_at': '2026-10-25T08:00:00Z',
} for i in range(1, 4)]

ADMIN_APPEALS = [{
    'id': f'a-{i}', 'entity_type': 'post', 'entity_id': str(i),
    'user': {'nickname': f'用户{i}', 'id': f'u-{i}'}, 'reason': '误判申诉说明文本',
    'status': 'pending', 'created_at': '2026-10-25T08:00:00Z',
} for i in range(1, 4)]

ADMIN_JOBS = [{
    'id': f'j-{i}', 'kind': 'moderate_post', 'status': 'review', 'attempts': 1,
    'payload': {'post_id': i}, 'created_at': '2026-10-25T08:00:00Z',
    'available_at': '2026-10-25T08:00:00Z',
} for i in range(1, 4)]

ADMIN_ACCOUNTS = [{
    'id': f'a-{i}', 'username': f'admin{i}', 'display_name': f'管理员{i}',
    'role': 'superadmin' if i == 1 else 'operator', 'status': 1,
    'mfa_enabled': i == 1, 'created_at': '2026-10-25T08:00:00Z',
    'last_login_at': '2026-10-25T08:00:00Z',
} for i in range(1, 3)]

ADMIN_TAGS = [{'id': i, 'name': f'标签{i}', 'post_count': i * 3} for i in range(1, 4)]

ADMIN_ACTIVITIES = [{
    'id': i, 'title': f'活动{i}', 'content': '活动说明正文。', 'image_url': None,
    'location': '大学生活动中心', 'start_at': '2026-10-25T08:00:00Z',
    'end_at': '2026-10-30T08:00:00Z', 'status': 1, 'created_at': '2026-10-25T08:00:00Z',
} for i in range(1, 3)]

TREND_DAYS = [{
    'date': f'2026-10-{d:02d}', 'posts': d, 'comments': d * 2, 'likes': d * 3,
    'new_users': d, 'active_users': d * 4,
} for d in range(1, 15)]


def ok(data):
    return {'code': 0, 'data': data}


def paged(rows):
    return ok({'items': rows, 'total': len(rows), 'page': 1, 'page_size': 20, 'has_more': False})


# ---------------------------------------------------------------- Mock 路由
def mock_api(path: str):
    """按路径返回 Mock 数据；未覆盖的接口返回空列表（前端有兜底空态）。"""
    # 管理台登录：契约与后端 app/routers/admin_auth.py 一致
    # {access_token, admin:{id, username, nickname}}
    if '/admin/auth/login' in path:
        return ok({'access_token': 'preview-admin-token',
                   'admin': {'id': 'a-1', 'username': 'boss', 'nickname': '走查管理员'}})
    # 管理台当前登录人：后端返回扁平结构 {id, display_name, source}
    if '/admin/auth/me' in path:
        return ok({'id': 'a-1', 'display_name': '走查管理员', 'source': 'preview'})
    if '/admin/stats/trends' in path:
        # 契约：{days: number, series: TrendPoint[]}
        return ok({'days': 14, 'series': TREND_DAYS})
    if '/admin/stats' in path:
        return ok({'pending_posts': 3, 'pending_reports': 2, 'posts_today': 12,
                   'total_posts': 156, 'total_users': 89, 'frozen_users': 1})
    if '/admin/posts/feature-candidates' in path:
        return ok({'items': ADMIN_POSTS[:2]})
    if '/admin/posts' in path:
        return paged(ADMIN_POSTS)
    if '/admin/users' in path:
        return paged(ADMIN_USERS)
    if '/admin/reports' in path:
        return paged(ADMIN_REPORTS)
    if '/admin/comments' in path:
        return paged(ADMIN_COMMENTS)
    if '/admin/parties' in path:
        return paged(ADMIN_PARTIES)
    if '/admin/banners' in path:
        return paged(ADMIN_BANNERS)
    if '/admin/announcements' in path:
        return paged(ADMIN_ANNOUNCEMENTS)
    if '/admin/logs' in path:
        return paged(ADMIN_LOGS)
    if '/admin/sensitive-words' in path:
        return paged(ADMIN_SENSITIVE)
    if '/admin/moderation-records' in path:
        return paged(ADMIN_MOD_RECORDS)
    if '/admin/student-verifications' in path:
        return paged(ADMIN_VERIFICATIONS)
    if '/admin/appeals' in path:
        return paged(ADMIN_APPEALS)
    if '/admin/moderation-jobs' in path:
        return paged(ADMIN_JOBS)
    if '/admin/admins' in path:
        return paged(ADMIN_ACCOUNTS)
    if '/admin/tags' in path:
        return paged(ADMIN_TAGS)
    if '/admin/activities' in path:
        return paged(ADMIN_ACTIVITIES)

    # --- 学生端 ---
    if '/auth/' in path or '/auth' in path:
        return ok({'access_token': 'preview-token', 'refresh_token': 'preview-refresh',
                   'token_type': 'bearer', 'expires_in': 900})
    if re.search(r'/users/[^/]+/profile', path):
        return ok(PROFILE)
    if '/users/' in path and path.endswith(('/following', '/followers')):
        return ok({'items': HOT_USERS, 'has_more': False})
    if '/users/' in path and path.endswith('/posts'):
        return paged(POSTS)
    if '/posts/hot' in path:
        return ok({'items': POSTS[:10]})
    if '/posts/search' in path:
        return ok({'items': POSTS[:3], 'total': 3, 'has_more': False})
    if '/posts/featured' in path:
        return ok({'items': POSTS[:2]})
    if '/posts/following' in path:
        return ok({'items': POSTS[:2]})
    if '/posts/' in path and 'comments' in path:
        return ok({'items': COMMENTS, 'total': len(COMMENTS), 'has_more': False})
    if re.search(r'/posts/\d+', path):
        return ok(POSTS[0])
    if path.endswith('/posts') or path.endswith('/posts/'):
        return ok({'items': POSTS, 'total': len(POSTS), 'has_more': False})
    if '/notifications/unread' in path or '/notification/unread' in path:
        return ok({'comment': 1, 'like': 0, 'favorite': 0, 'group': 0, 'moderation': 0})
    if '/notifications' in path:
        return ok({'items': NOTIFICATIONS, 'has_more': False})
    if '/parties/summary' in path:
        return ok({'total_members': 12})
    if '/me/parties' in path:
        return ok({'items': PARTIES[:1], 'next_cursor': None, 'has_more': False})
    if '/parties' in path:
        return ok({'items': PARTIES, 'next_cursor': None, 'has_more': False})
    if path.endswith('/tags'):
        return ok(TAGS)
    if '/user/blocks' in path:
        return ok({'items': [{'id': USER_ID, 'nickname': '被拉黑同学'}], 'has_more': False})
    if '/appeals' in path:
        return ok({'items': [{'id': 'a-1', 'entity_type': 'post', 'entity_id': '1',
                              'reason': '误判申诉：内容为课程作业讨论', 'status': 'pending',
                              'created_at': '2026-10-21T08:00:00Z'}]})
    if '/student-verifications/challenge' in path:
        return ok({'verification_id': 'v-1', 'challenge_id': 'c-1', 'code': '4821',
                   'expires_at': '2026-10-25T08:00:00Z'})
    if '/student-verifications/me' in path:
        return ok({'enabled': True, 'school_name': '示例大学', 'verification': None})
    if '/user/hot-ranking' in path:
        return ok({'items': HOT_USERS})
    if '/user/checkin/status' in path:
        return ok({'checked_in': False, 'continuous_days': 0})
    if '/user/profile' in path:
        return ok(PROFILE)
    if '/banners' in path:
        return ok({'items': []})
    if '/activities' in path or '/activity' in path:
        return ok({'id': 1, 'title': '秋季摄影展征稿', 'image_url': None,
                   'summary': '银杏主题，拍摄校园一角即可', 'content': '秋季摄影展征稿说明正文。',
                   'location': '大学生活动中心', 'start_at': '2026-10-20T08:00:00Z',
                   'end_at': '2026-10-30T08:00:00Z', 'status': 1,
                   'created_at': '2026-10-19T08:00:00Z'})
    if '/stats' in path:
        return ok({'posts': 12, 'comments': 8, 'likes': 20, 'favorites': 5})
    return ok({'items': []})


# ---------------------------------------------------------------- HTTP 服务
class PreviewHandler(SimpleHTTPRequestHandler):
    dist_dir = ''
    spa_fallback = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=self.dist_dir, **kwargs)

    def _send_json(self, payload, status=200, cookies=None):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        for cookie in cookies or []:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith('/api/'):
            self._send_json(mock_api(parsed.path))
            return
        if self.spa_fallback:
            clean = parsed.path.lstrip('/')
            full = os.path.join(self.dist_dir, clean)
            if not (clean and os.path.exists(full) and not os.path.isdir(full)):
                self.path = '/index.html'
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith('/api/'):
            length = int(self.headers.get('Content-Length') or 0)
            if length:
                self.rfile.read(length)
            cookies = None
            if parsed.path.endswith('/admin/auth/login'):
                # 管理台用 sw_admin_csrf Cookie 维持会话（刷新后不丢登录态）
                cookies = ['sw_admin_csrf=preview-admin-csrf; Path=/; SameSite=Lax']
            self._send_json(mock_api(parsed.path), cookies=cookies)
            return
        self._send_json({'code': 0, 'data': {}})

    def do_PUT(self):
        self.do_POST()

    def do_DELETE(self):
        self.do_POST()

    def log_message(self, fmt, *args):
        pass


def serve(target: str, port: int):
    if target == 'web':
        dist = os.path.join(ROOT, 'frontend', 'dist', 'build', 'h5')
        spa = False
    else:
        dist = os.path.join(ROOT, 'admin-frontend', 'dist')
        spa = True
    if not os.path.isdir(dist):
        print(f'Error: 未找到构建产物 {dist}', file=sys.stderr)
        print('请先执行：cd frontend && npm run build:h5   （管理台：cd admin-frontend && npm run build）',
              file=sys.stderr)
        sys.exit(1)

    handler = type('BoundPreviewHandler', (PreviewHandler,),
                   {'dist_dir': dist, 'spa_fallback': spa})
    httpd = ThreadingHTTPServer(('127.0.0.1', port), handler)
    httpd.daemon_threads = True
    print(f'{"学生端 H5" if target == "web" else "管理后台"}预览: http://127.0.0.1:{port}')
    print(f'  静态目录: {dist}')
    print('  /api/v1/** 由本地 Mock 提供（未连接真实后端）')
    if target == 'admin':
        print('  管理台演示登录：任意用户名 + 任意密码，动态码留空即可（本地 Mock，不校验凭据）')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止')


def main():
    parser = argparse.ArgumentParser(description='SchoolWall 本地界面预览（Mock 数据）')
    parser.add_argument('target', choices=['web', 'admin'], help='web=学生端H5，admin=管理后台')
    parser.add_argument('--port', type=int, default=None, help='端口（默认 web=5173, admin=5174）')
    args = parser.parse_args()
    port = args.port or (5173 if args.target == 'web' else 5174)
    serve(args.target, port)


if __name__ == '__main__':
    main()
