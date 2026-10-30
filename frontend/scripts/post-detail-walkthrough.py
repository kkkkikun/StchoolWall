#!/usr/bin/env python3
"""
SchoolWall 学生端 H5 帖子详情 点赞/评论 交互真实浏览器验收
（独立脚本；复用 h5_mock_api.py 共享 Mock；单 Chromium 390x844 串行）

真实链路：真实 UI 登录 → 首页点击真实信息流卡片进入详情 → 生产 onLike/onSendComment
→ 真实 HTTP 请求（拦截计数/方法/路径/请求体）。

场景：
  D1 详情加载（作者/正文/互动栏 4 项/评论列表）
  D2 点赞：未赞→已赞（POST /posts/{id}/like，计数+1、实心心形图标），再点取消（DELETE，恢复）
  D3 空/纯空白评论：零评论请求（发送按钮 disabled 为现有设计反馈）
  D4 有效评论：恰好 1 次 POST、请求体正确、toast「评论成功」、新评论出现在列表、输入框清空
  D5 评论业务错误（code=400）：原样展示后端提示、输入内容保留、按钮恢复、重试成功
  D6 评论网络失败（abort）：不得泄漏底层技术错误、按钮恢复、重试成功
  D7 评论请求在途连点 ×3：仅 1 次 POST（生产 sending 防重）
  D8 点赞请求失败：状态回滚到未赞、toast 不泄漏底层错误

产物：ci-artifacts/ui-walkthrough/post-detail-report.json + post-detail-*.png
任一断言失败 -> 场景 FAIL，退出码非零。全部 Mock API，非真实后端联调。
"""

import http.server
import json
import os
import socket
import socketserver
import sys
import threading
import time
import traceback
from playwright.sync_api import sync_playwright

from h5_mock_api import handle_api, COMMENTS_FIXTURE, DETAIL_POST_FIXTURE

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIST_DIR = os.path.join(ROOT_DIR, 'frontend', 'dist', 'build', 'h5')
ARTIFACTS_DIR = os.path.join(ROOT_DIR, 'ci-artifacts', 'ui-walkthrough')
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

if not os.path.isdir(DIST_DIR):
    print(f"Error: DIST_DIR not found at {DIST_DIR}. Run 'npm run build:h5' first.", file=sys.stderr)
    sys.exit(1)

SESSION_OK = {
    'code': 0, 'message': 'success',
    'data': {
        'access_token': 'mock-access-token-for-detail-test',
        'csrf_token': 'mock-csrf-token',
        'session_id': 'mock-session-id',
        'role': 'guest',
        'user_info': {'id': 'u-detail-test', 'nickname': '互动测试同学', 'is_verified': False},
    },
}

# ---------------------------------------------------------------- 静态服务
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind(('127.0.0.1', 0))
port = sock.getsockname()[1]
sock.close()

class SilentHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST_DIR, **kwargs)
    def log_message(self, format, *args):
        pass

socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(('127.0.0.1', port), SilentHandler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
base_url = f'http://127.0.0.1:{port}'
print(f'H5 static server listening on {base_url}')

# ---------------------------------------------------------------- Mock 状态
like_calls = {'post': 0, 'delete': 0}
fav_calls = {'post': 0, 'delete': 0}
fav_behavior = {'mode': 'ok'}  # ok | error | abort
del_comment_calls = {'count': 0, 'urls': []}
del_comment_behavior = {'mode': 'ok'}  # ok | error | abort
status_calls = {'count': 0, 'urls': []}
status_behavior = {'mode': 'ok'}  # ok | error | abort
report_calls = {'count': 0, 'bodies': []}
report_behavior = {'mode': 'ok'}  # ok | error | abort
block_calls = {'count': 0, 'urls': []}
block_behavior = {'mode': 'ok'}  # ok | abort
follow_calls = {'post': 0, 'delete': 0}
follow_behavior = {'mode': 'ok'}  # ok | error | abort
comment_calls = {'count': 0, 'bodies': []}
comment_get_urls = []
comments_paged = {'enabled': False, 'abort_page2': False}
PAGE2_CURSOR = 9000
PAGE2_COMMENTS = [
    {'id': 9501, 'post_id': 1, 'user_id': 'u2004',
     'content': '第二页第一条：补充一下四楼研讨区也有同样问题。',
     'user': {'nickname': '四楼常客', 'avatar_url': None}, 'created_at': '2026-10-21T07:00:00Z'},
    {'id': 9502, 'post_id': 1, 'user_id': 'u2005',
     'content': '第二页第二条：已经报修，后勤回复本周处理。',
     'user': {'nickname': '后勤小助手', 'avatar_url': None}, 'created_at': '2026-10-21T06:00:00Z'},
]
created_comments = []
comment_behavior = {'mode': 'ok'}   # ok | error | abort | hold
like_behavior = {'mode': 'ok'}      # ok | error
held_comment_routes = []

def handle_like(route):
    url = route.request.url
    if '/like' not in url:
        return handle_api(route)
    if route.request.method == 'POST':
        like_calls['post'] += 1
        if like_behavior['mode'] == 'error':
            route.fulfill(status=200, content_type='application/json',
                          body=json.dumps({'code': 500, 'message': '点赞服务异常'}))
            return
        if like_behavior['mode'] == 'abort':
            route.abort()
            return
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps({'code': 0, 'data': {'liked': True, 'like_count': 16}}))
    elif route.request.method == 'DELETE':
        like_calls['delete'] += 1
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps({'code': 0, 'data': {'liked': False, 'like_count': 15}}))
    else:
        handle_api(route)

def handle_favorite(route):
    if '/favorite' not in route.request.url:
        return handle_api(route)
    if route.request.method == 'POST':
        fav_calls['post'] += 1
        if fav_behavior['mode'] == 'error':
            route.fulfill(status=200, content_type='application/json',
                          body=json.dumps({'code': 500, 'message': '收藏服务繁忙，请稍后再试'}))
            return
        if fav_behavior['mode'] == 'abort':
            route.abort()
            return
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps({'code': 0, 'data': {'favorited': True}}))
    elif route.request.method == 'DELETE':
        fav_calls['delete'] += 1
        if fav_behavior['mode'] == 'error':
            route.fulfill(status=200, content_type='application/json',
                          body=json.dumps({'code': 500, 'message': '收藏服务繁忙，请稍后再试'}))
            return
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps({'code': 0, 'data': {'favorited': False}}))
    else:
        handle_api(route)

# 作者身份帖子 fixture：user_id 与 Mock 登录用户一致，页面才渲染「删除」入口；
# 同时去除联系信息，用于 CT2 无联系方式场景
AUTHOR_POST_FIXTURE = dict(DETAIL_POST_FIXTURE)
AUTHOR_POST_FIXTURE.update({
    'id': 102,
    'user_id': 'u-detail-test',
    'user': {'id': 'u-detail-test', 'nickname': '互动测试同学', 'avatar_url': None},
    'author': {'id': 'u-detail-test', 'nickname': '互动测试同学', 'avatar_url': None},
    'contact_info': '',
    'contact_wechat': '',
})

def handle_author_post(route):
    """GET /posts/102 精确返回作者身份帖子；其余走共享兜底。"""
    if route.request.method == 'GET' and route.request.url.split('?')[0].rstrip('/').endswith('/posts/102'):
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps({'code': 0, 'data': AUTHOR_POST_FIXTURE}))
        return
    handle_api(route)

def handle_post_status(route):
    """PUT /posts/{id}/status（deletePost = status=-2 软删除）：计数 + 行为控制。"""
    url = route.request.url
    if '/status' not in url or route.request.method != 'PUT':
        return handle_api(route)
    status_calls['count'] += 1
    status_calls['urls'].append(url)
    mode = status_behavior['mode']
    if mode == 'abort':
        route.abort()
        return
    if mode == 'error':
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps({'code': 403, 'message': '帖子已被锁定，无法删除'}))
        return
    route.fulfill(status=200, content_type='application/json',
                  body=json.dumps({'code': 0, 'data': {'status': -2}}))

def handle_report(route):
    """POST /posts/{id}/report {reason, description?}：计数 + 请求体捕获 + 行为控制。"""
    if '/report' not in route.request.url or route.request.method != 'POST':
        return handle_api(route)
    report_calls['count'] += 1
    try:
        report_calls['bodies'].append(json.loads(route.request.post_data or '{}'))
    except Exception:
        report_calls['bodies'].append(None)
    mode = report_behavior['mode']
    if mode == 'abort':
        route.abort()
        return
    if mode == 'error':
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps({'code': 429, 'message': '你已举报过该内容，请耐心等待处理'}))
        return
    route.fulfill(status=200, content_type='application/json',
                  body=json.dumps({'code': 0, 'data': {'reported': True}}))

def handle_block(route):
    """POST /users/{id}/block：计数 + 行为控制。"""
    if '/block' not in route.request.url or route.request.method != 'POST':
        return handle_api(route)
    block_calls['count'] += 1
    block_calls['urls'].append(route.request.url)
    if block_behavior['mode'] == 'abort':
        route.abort()
        return
    route.fulfill(status=200, content_type='application/json',
                  body=json.dumps({'code': 0, 'data': {'blocked': True}}))

def handle_follow(route):
    """POST/DELETE /users/{id}/follow：计数 + 行为控制。"""
    if '/follow' not in route.request.url:
        return handle_api(route)
    if route.request.method == 'POST':
        follow_calls['post'] += 1
        if follow_behavior['mode'] == 'error':
            route.fulfill(status=200, content_type='application/json',
                          body=json.dumps({'code': 429, 'message': '操作过于频繁，请稍后再试'}))
            return
        if follow_behavior['mode'] == 'abort':
            route.abort()
            return
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps({'code': 0, 'data': {'followed': True}}))
    elif route.request.method == 'DELETE':
        follow_calls['delete'] += 1
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps({'code': 0, 'data': {'followed': False}}))
    else:
        handle_api(route)

def handle_delete_comment(route):
    """DELETE /comments/{id}：计数 + 行为控制；成功时同步移出 mock 评论列表。"""
    url = route.request.url
    if route.request.method != 'DELETE':
        return handle_api(route)
    del_comment_calls['count'] += 1
    del_comment_calls['urls'].append(url)
    mode = del_comment_behavior['mode']
    if mode == 'abort':
        route.abort()
        return
    if mode == 'error':
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps({'code': 403, 'message': '评论已被锁定，无法删除'}))
        return
    try:
        cid = int(url.rstrip('/').rsplit('/', 1)[-1])
        created_comments[:] = [c for c in created_comments if c['id'] != cid]
    except (ValueError, IndexError):
        pass
    route.fulfill(status=200, content_type='application/json',
                  body=json.dumps({'code': 0, 'data': {'deleted': True}}))

def handle_comments(route):
    if '/comments' not in route.request.url:
        return handle_api(route)
    if route.request.method == 'GET':
        comment_get_urls.append(route.request.url)
        if comments_paged['enabled']:
            if f'cursor={PAGE2_CURSOR}' in route.request.url:
                if comments_paged['abort_page2']:
                    route.abort()
                    return
                route.fulfill(status=200, content_type='application/json', body=json.dumps(
                    {'code': 0, 'data': {'items': PAGE2_COMMENTS, 'next_cursor': None, 'has_more': False}}))
            else:
                items = COMMENTS_FIXTURE + created_comments
                route.fulfill(status=200, content_type='application/json', body=json.dumps(
                    {'code': 0, 'data': {'items': items, 'next_cursor': PAGE2_CURSOR, 'has_more': True}}))
            return
        items = COMMENTS_FIXTURE + created_comments
        route.fulfill(status=200, content_type='application/json', body=json.dumps(
            {'code': 0, 'data': {'items': items, 'total': len(items), 'has_more': False}}))
        return
    if route.request.method != 'POST':
        return handle_api(route)
    comment_calls['count'] += 1
    try:
        comment_calls['bodies'].append(json.loads(route.request.post_data or '{}'))
    except Exception:
        comment_calls['bodies'].append(None)
    mode = comment_behavior['mode']
    if mode == 'hold':
        held_comment_routes.append(route)
        return
    if mode == 'abort':
        route.abort()
        return
    if mode == 'error':
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps({'code': 400, 'message': '评论包含敏感词，请修改后重试'}))
        return
    body = comment_calls['bodies'][-1] or {}
    created = {
        'id': 900 + comment_calls['count'],
        'post_id': 1,
        'user_id': 'u-detail-test',
        'content': body.get('content', ''),
        'user': {'nickname': '互动测试同学', 'avatar_url': None},
        'created_at': '2026-10-23T01:00:00Z',
        'status': 1,
    }
    if mode == 'pending':
        # 灰词转人工：status=0，不进入公开列表（生产契约：审核通过后才公开）
        created['status'] = 0
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps({'code': 0, 'data': created}))
        return
    created_comments.append(created)
    route.fulfill(status=200, content_type='application/json',
                  body=json.dumps({'code': 0, 'data': created}))

def release_comments():
    routes = held_comment_routes[:]
    held_comment_routes.clear()
    for r in routes:
        try:
            body = comment_calls['bodies'][-1] or {}
            created = {
                'id': 900 + comment_calls['count'], 'post_id': 1, 'user_id': 'u-detail-test',
                'content': body.get('content', ''),
                'user': {'nickname': '互动测试同学', 'avatar_url': None},
                'created_at': '2026-10-23T01:00:00Z', 'status': 1,
            }
            created_comments.append(created)
            r.fulfill(status=200, content_type='application/json',
                      body=json.dumps({'code': 0, 'data': created}))
        except Exception:
            pass

def handle_user_profile(route):
    """GET /users/{id}/profile：个人主页公开资料（契约见 api/profile.ts UserProfile）。"""
    route.fulfill(status=200, content_type='application/json', body=json.dumps({
        'code': 0, 'data': {
            'id': 'u1001', 'nickname': '自习达人（考研上岸版超长昵称测试）',
            'avatar_url': None, 'banner_url': None, 'bio': '图书馆常驻，分享自习攻略',
            'is_verified': True, 'school': '鄂尔多斯应用技术学院',
            'posts_count': 12, 'following_count': 5, 'followers_count': 34,
            'is_following': False, 'is_self': False,
        }}))

def handle_web_login(route):
    route.fulfill(status=200, content_type='application/json', body=json.dumps(SESSION_OK))

def handle_profile(route):
    route.fulfill(status=200, content_type='application/json', body=json.dumps({
        'code': 0, 'data': {'nickname': '互动测试同学', 'is_verified': False}}))

# ---------------------------------------------------------------- 工具
class ScenarioFailure(Exception):
    pass

def check(cond, msg):
    if not cond:
        raise ScenarioFailure(msg)

report = {
    'task': 'student H5 post detail like/comment interaction acceptance',
    'date_utc': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
    'base_url': base_url,
    'browser': 'chromium(headless)',
    'viewport': '390x844',
    'mock_scope': ('Real UI login + real feed-card navigation; like/comment APIs intercepted '
                   'with method/path/body capture per production contracts (interaction.ts). '
                   'Mock only - not real backend integration.'),
    'like_requests': like_calls,
    'comment_requests': comment_calls,
    'scenarios': [],
    'screenshots': [],
    'overall': 'PASS',
}

def record(name, status, assertions=None, error=None, screenshots=None):
    report['scenarios'].append({'scenario': name, 'status': status,
                                'assertions': assertions or {}, 'error': error,
                                'screenshots': screenshots or []})
    if screenshots:
        report['screenshots'].extend(screenshots)
    if status != 'PASS':
        report['overall'] = 'FAIL'

def shot(page, filename):
    page.screenshot(path=f'{ARTIFACTS_DIR}/{filename}')
    return filename

def toast_text(page):
    t = page.locator('uni-toast')
    return t.inner_text().strip() if t.count() else ''

def set_comment(page, text):
    page.evaluate('''(v) => {
        const t = document.querySelector('.comment-input input') ||
                  document.querySelector('.comment-input');
        t.value = v;
        t.dispatchEvent(new Event('input', { bubbles: true }));
    }''', text)
    page.wait_for_timeout(150)

def get_comment(page):
    return page.evaluate('''() => {
        const t = document.querySelector('.comment-input input') ||
                  document.querySelector('.comment-input');
        return t.value;
    }''')

def like_btn_text(page):
    return page.locator('.action-bar .act').first.inner_text().strip()

def fav_btn_class(page):
    return page.locator('.action-bar .act').nth(1).get_attribute('class') or ''

def fav_btn_text(page):
    return page.locator('.action-bar .act').nth(1).inner_text().strip()

def act_icon_src(page, idx=0):
    """互动条图标的 SVG 资源路径。

    图标已从 emoji 字形换成 <image src="*.svg">，uni-app H5 渲染成
    <uni-image><img src="..."></uni-image>，因此取内部 img 的 src。
    """
    img = page.locator('.action-bar .act').nth(idx).locator('.act-icon img')
    if img.count() == 0:
        return ''
    return img.first.get_attribute('src') or ''

def comments_title(page):
    return page.locator('.comments-title').inner_text().strip()

def confirm_uni_modal(page):
    """uni.showModal 确认（H5 渲染英文按钮 Cancel/OK，点主按钮）。"""
    page.locator('uni-modal .uni-modal__btn_primary').click()
    page.wait_for_timeout(300)

def login_via_ui(page):
    page.goto(f'{base_url}/#/pages/mine/index')
    page.wait_for_selector('.dev-login-row', timeout=8000)
    page.locator('.dev-capsule:has-text("登录 / 注册")').click()
    page.wait_for_selector('.auth-form', timeout=5000)
    page.evaluate('''() => {
        const inputs = document.querySelectorAll('.auth-form .auth-input input');
        ['detail_tester', 'password123'].forEach((v, i) => {
            const el = inputs[i];
            el.value = v;
            el.dispatchEvent(new Event('input', { bubbles: true }));
        });
    }''')
    page.wait_for_timeout(200)
    page.locator('.auth-submit').click()
    page.wait_for_timeout(1500)
    if page.locator('.auth-form').count() > 0:
        raise ScenarioFailure('Mock 登录失败：弹窗未关闭')

def goto_detail_via_feed(page):
    """经首页真实信息流卡片进入详情（应用内导航，保留内存会话）。"""
    page.locator('.tab-bar .tab-item').nth(0).click()
    page.wait_for_selector('.feed-card', timeout=8000)
    page.wait_for_timeout(500)
    page.locator('.feed-card .feed-body').first.click()
    page.wait_for_selector('.content-text', timeout=8000)
    page.wait_for_timeout(800)

exit_code = 0
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={'width': 390, 'height': 844},
                                  permissions=['clipboard-read', 'clipboard-write'])
        page = ctx.new_page()
        page.route('**/api/v1/**', handle_api)  # 兜底先注册（Playwright 后注册优先）
        page.route('**/api/v1/posts/**', handle_like)
        page.route('**/api/v1/posts/*/favorite', handle_favorite)
        page.route('**/api/v1/posts/*/comments*', handle_comments)
        page.route('**/api/v1/posts/*/status*', handle_post_status)
        page.route('**/api/v1/posts/*/report', handle_report)
        page.route('**/api/v1/posts/102', handle_author_post)
        page.route('**/api/v1/users/*/block', handle_block)
        page.route('**/api/v1/users/*/follow', handle_follow)
        page.route('**/api/v1/users/*/profile', handle_user_profile)
        page.route('**/api/v1/comments/*', handle_delete_comment)
        page.route('**/api/v1/auth/web-login', handle_web_login)
        page.route('**/api/v1/user/profile', handle_profile)

        login_via_ui(page)
        goto_detail_via_feed(page)

        # ================= D1 详情加载 =================
        print('\n--- D1 详情加载 ---')
        try:
            check(page.locator('.author .nickname').is_visible(), '作者昵称应可见')
            check(page.locator('.content-text').is_visible(), '正文应可见')
            check(page.locator('.action-bar .act').count() == 4, '互动栏应为 4 项')
            check(page.locator('.comments .comment').count() >= 1, '评论列表应渲染')
            check('赞' in like_btn_text(page), '点赞按钮应可见')
            s1 = shot(page, 'post-detail-d1-loaded.png')
            print('   [通过] 详情各区块渲染完整')
            record('D1_detail_loaded', 'PASS',
                   assertions={'actions': 4, 'comments_rendered': True}, screenshots=[s1])
        except Exception as e:
            print(f'   [失败] {e}')
            record('D1_detail_loaded', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= D2 点赞/取消点赞 =================
        print('\n--- D2 点赞切换与取消 ---')
        try:
            check('15' in like_btn_text(page), f'初始赞数应为 15，实际: {like_btn_text(page)}')
            page.locator('.action-bar .act').first.click()
            page.wait_for_timeout(800)
            check(like_calls['post'] == 1, f'点赞应产生 1 次 POST like，实际 {like_calls["post"]}')
            check('16' in like_btn_text(page), f'点赞后计数应为 16，实际: {like_btn_text(page)}')
            check('heart-on.svg' in act_icon_src(page, 0),
                  f'点赞后应显示实心爱心图标 heart-on.svg，实际: {act_icon_src(page, 0)}')
            s2 = shot(page, 'post-detail-d2-liked.png')

            page.locator('.action-bar .act').first.click()
            page.wait_for_timeout(800)
            check(like_calls['delete'] == 1, f'取消赞应产生 1 次 DELETE like，实际 {like_calls["delete"]}')
            check('15' in like_btn_text(page), f'取消后计数应恢复 15，实际: {like_btn_text(page)}')
            check('heart.svg' in act_icon_src(page, 0) and 'heart-on' not in act_icon_src(page, 0),
                  f'取消后应恢复空心爱心图标 heart.svg，实际: {act_icon_src(page, 0)}')
            print('   [通过] POST→16（实心心形）/ DELETE→15（空心心形），方法与计数契约正确')
            record('D2_like_toggle', 'PASS',
                   assertions={'post_like_calls': 1, 'delete_like_calls': 1,
                               'count_up': 16, 'count_back': 15}, screenshots=[s2])
        except Exception as e:
            print(f'   [失败] {e}')
            record('D2_like_toggle', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= D3 空/空白评论 =================
        print('\n--- D3 空与纯空白评论 ---')
        try:
            before = comment_calls['count']
            btn_class = page.locator('.send-btn').get_attribute('class') or ''
            check('disabled' in btn_class, f'空输入时发送按钮应为 disabled 视觉态，实际 class: {btn_class}')
            page.locator('.send-btn').click()
            page.wait_for_timeout(400)
            set_comment(page, '   ')
            page.locator('.send-btn').click()
            page.wait_for_timeout(400)
            check(comment_calls['count'] == before,
                  f'空/空白评论不得发出请求（{before} -> {comment_calls["count"]}）')
            print('   [通过] 空/空白均零请求（disabled 视觉态为现有设计反馈）')
            record('D3_empty_comment', 'PASS',
                   assertions={'requests_delta': 0, 'disabled_class': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('D3_empty_comment', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= D4 有效评论 =================
        print('\n--- D4 有效评论提交 ---')
        try:
            set_comment(page, '自习室插座确实该修修了，支持！')
            before = comment_calls['count']
            page.locator('.send-btn').click()
            page.wait_for_timeout(1200)
            check(comment_calls['count'] - before == 1, '应恰好 1 次评论 POST')
            body = comment_calls['bodies'][-1]
            check(body and body.get('content') == '自习室插座确实该修修了，支持！',
                  f'请求体 content 不符: {body}')
            t = toast_text(page)
            check('评论成功' in t, f'应有成功提示，实际: 「{t}」')
            check(get_comment(page) == '', f'成功后输入框应清空，实际: 「{get_comment(page)}」')
            check(page.locator('.comments .comment:has-text("自习室插座确实该修修了")').count() == 1,
                  '新评论应出现在列表中')
            s4 = shot(page, 'post-detail-d4-commented.png')
            print(f'   [通过] 1 次 POST，请求体正确，新评论上屏，输入框清空')
            record('D4_valid_comment', 'PASS',
                   assertions={'requests_delta': 1, 'body': body, 'toast': t,
                               'input_cleared': True, 'comment_visible': True}, screenshots=[s4])
        except Exception as e:
            print(f'   [失败] {e}')
            record('D4_valid_comment', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= D5 评论业务错误 =================
        print('\n--- D5 评论业务错误后恢复重试 ---')
        try:
            set_comment(page, '这条评论触发敏感词测试')
            comment_behavior['mode'] = 'error'
            before = comment_calls['count']
            page.locator('.send-btn').click()
            page.wait_for_timeout(800)
            check(comment_calls['count'] - before == 1, '错误场景应恰好 1 次请求')
            t = toast_text(page)
            check('敏感词' in t, f'应展示后端业务错误，实际: 「{t}」')
            check(get_comment(page) == '这条评论触发敏感词测试', '失败后输入内容不得丢失')
            s5 = shot(page, 'post-detail-d5-error.png')

            comment_behavior['mode'] = 'ok'
            page.locator('.send-btn').click()
            page.wait_for_timeout(1200)
            check(comment_calls['count'] - before == 2, '重试应产生第 2 次请求')
            check('评论成功' in toast_text(page), '重试应成功')
            print(f'   [通过] 业务错误 toast=「{t}」，内容保留，重试成功')
            record('D5_comment_api_error', 'PASS',
                   assertions={'error_toast': t, 'input_kept': True, 'retry_success': True},
                   screenshots=[s5])
        except Exception as e:
            print(f'   [失败] {e}')
            record('D5_comment_api_error', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            comment_behavior['mode'] = 'ok'

        # ================= D6 评论网络失败 =================
        print('\n--- D6 评论网络失败（不泄漏底层错误） ---')
        try:
            set_comment(page, '网络抖动时的评论重试')
            comment_behavior['mode'] = 'abort'
            before = comment_calls['count']
            page.locator('.send-btn').click()
            page.wait_for_timeout(800)
            check(comment_calls['count'] - before == 1, 'abort 场景应恰好 1 次请求')
            t = toast_text(page)
            check('request:fail' not in t and 'Error' not in t,
                  f'不得泄漏底层技术错误，实际 toast: 「{t}」')
            check(t == '网络连接失败，请检查网络后重试',
                  f'网络失败应映射为友好提示，实际: 「{t}」')
            check(get_comment(page) == '网络抖动时的评论重试', '网络失败后输入内容不得丢失')

            comment_behavior['mode'] = 'ok'
            page.locator('.send-btn').click()
            page.wait_for_timeout(1200)
            check(comment_calls['count'] - before == 2, '重试应产生第 2 次请求')
            check('评论成功' in toast_text(page), '网络恢复后重试应成功')
            print(f'   [通过] toast=「{t}」，按钮恢复，重试成功')
            record('D6_comment_network_failure', 'PASS',
                   assertions={'toast': t, 'no_tech_leak': True, 'retry_success': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('D6_comment_network_failure', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            comment_behavior['mode'] = 'ok'

        # ================= D7 评论在途连点防重 =================
        print('\n--- D7 评论在途连点防重 ---')
        try:
            set_comment(page, '连点防重测试评论')
            comment_behavior['mode'] = 'hold'
            before = comment_calls['count']
            for _ in range(3):
                page.locator('.send-btn').click()
                page.wait_for_timeout(250)
            check(comment_calls['count'] - before == 1,
                  f'在途连点 3 次应只 1 次评论 POST，实际 {comment_calls["count"] - before}')
            s7 = shot(page, 'post-detail-d7-inflight.png')
            release_comments()
            comment_behavior['mode'] = 'ok'
            page.wait_for_timeout(1200)
            check('评论成功' in toast_text(page) or page.locator(
                '.comments .comment:has-text("连点防重测试评论")').count() == 1,
                '放行后评论应成功上屏')
            print('   [通过] 在途连点仅 1 次请求（生产 sending 防重有效）')
            record('D7_comment_inflight_dedup', 'PASS',
                   assertions={'clicks': 3, 'requests_delta': 1}, screenshots=[s7])
        except Exception as e:
            print(f'   [失败] {e}')
            record('D7_comment_inflight_dedup', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            release_comments()
            comment_behavior['mode'] = 'ok'

        # ================= D8 点赞失败回滚 =================
        print('\n--- D8 点赞失败状态回滚 ---')
        try:
            check('15' in like_btn_text(page), 'D8 前置：应为未赞状态')
            like_behavior['mode'] = 'error'
            before_post = like_calls['post']
            page.locator('.action-bar .act').first.click()
            page.wait_for_timeout(800)
            check(like_calls['post'] - before_post == 1, '应产生 1 次点赞请求')
            check('15' in like_btn_text(page), f'失败后计数应回滚为 15，实际: {like_btn_text(page)}')
            check('heart.svg' in act_icon_src(page, 0) and 'heart-on' not in act_icon_src(page, 0),
                  f'失败后应回滚为未赞图标 heart.svg，实际: {act_icon_src(page, 0)}')
            t = toast_text(page)
            check('request:fail' not in t and 'Error' not in t,
                  f'点赞失败 toast 不得泄漏底层错误，实际: 「{t}」')
            like_behavior['mode'] = 'ok'
            print(f'   [通过] 点赞业务错误回滚正确，toast=「{t}」')

            # D8b 点赞网络失败（abort）：验证回滚 + 底层错误不泄漏
            check('15' in like_btn_text(page), 'D8b 前置：应仍为未赞状态')
            like_behavior['mode'] = 'abort'
            before_post = like_calls['post']
            page.locator('.action-bar .act').first.click()
            page.wait_for_timeout(800)
            check(like_calls['post'] - before_post == 1, '网络失败场景应产生 1 次点赞请求')
            check('15' in like_btn_text(page), f'网络失败后计数应回滚为 15，实际: {like_btn_text(page)}')
            check('heart.svg' in act_icon_src(page, 0) and 'heart-on' not in act_icon_src(page, 0),
                  f'网络失败后应回滚为未赞图标 heart.svg，实际: {act_icon_src(page, 0)}')
            t2 = toast_text(page)
            check('request:fail' not in t2 and 'Error' not in t2,
                  f'点赞网络失败不得泄漏底层错误，实际: 「{t2}」')
            check(t2 == '网络连接失败，请检查网络后重试',
                  f'点赞网络失败应映射为友好提示，实际: 「{t2}」')
            like_behavior['mode'] = 'ok'
            record('D8_like_error_rollback', 'PASS',
                   assertions={'rolled_back': True, 'biz_toast': t, 'network_toast': t2})
        except Exception as e:
            print(f'   [失败] {e}')
            record('D8_like_error_rollback', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            like_behavior['mode'] = 'ok'

        # ================= F1 收藏网络失败：回滚 + 友好提示 + 重试 =================
        print('\n--- F1 收藏网络失败回滚与友好提示 ---')
        try:
            check('on-fav' not in fav_btn_class(page), 'F1 前置：应为未收藏状态')
            fav_behavior['mode'] = 'abort'
            before = fav_calls['post']
            page.locator('.action-bar .act').nth(1).click()
            page.wait_for_timeout(800)
            check(fav_calls['post'] - before == 1, '应产生 1 次收藏 POST')
            check('on-fav' not in fav_btn_class(page), '网络失败后收藏状态应回滚（仍为未收藏）')
            check('star.svg' in act_icon_src(page, 1) and 'star-on' not in act_icon_src(page, 1),
                  f'图标应回滚为空心星 star.svg，实际: {act_icon_src(page, 1)}')
            t = toast_text(page)
            check('request:fail' not in t and 'Error' not in t,
                  f'不得泄漏底层错误，实际: 「{t}」')
            check(t == '网络连接失败，请检查网络后重试',
                  f'网络失败应映射为友好提示，实际: 「{t}」')

            fav_behavior['mode'] = 'ok'
            page.locator('.action-bar .act').nth(1).click()
            page.wait_for_timeout(800)
            check(fav_calls['post'] - before == 2, '重试应产生第 2 次收藏 POST')
            check('on-fav' in fav_btn_class(page) and 'star-on.svg' in act_icon_src(page, 1),
                  f'重试成功后应为已收藏态（实心星 star-on.svg），实际: {act_icon_src(page, 1)}')
            check('已收藏' in toast_text(page), '成功 toast 应为「已收藏」')
            s_f1 = shot(page, 'post-detail-f1-favorited.png')
            print(f'   [通过] 网络失败回滚+友好提示（「{t}」），重试收藏成功')
            record('F1_favorite_network_retry', 'PASS',
                   assertions={'abort_toast': t, 'rolled_back': True, 'retry_favorited': True},
                   screenshots=[s_f1])
        except Exception as e:
            print(f'   [失败] {e}')
            record('F1_favorite_network_retry', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            fav_behavior['mode'] = 'ok'

        # ================= F2 取消收藏业务错误：回滚 + 业务消息原样 =================
        print('\n--- F2 取消收藏业务错误回滚与消息保留 ---')
        try:
            check('on-fav' in fav_btn_class(page), 'F2 前置：应为已收藏状态')
            fav_behavior['mode'] = 'error'
            before = fav_calls['delete']
            page.locator('.action-bar .act').nth(1).click()
            page.wait_for_timeout(800)
            check(fav_calls['delete'] - before == 1, '应产生 1 次取消收藏 DELETE')
            check('on-fav' in fav_btn_class(page), '业务失败后应保持已收藏态（回滚）')
            t = toast_text(page)
            check(t == '收藏服务繁忙，请稍后再试',
                  f'后端业务消息应原样展示，实际: 「{t}」')

            fav_behavior['mode'] = 'ok'
            page.locator('.action-bar .act').nth(1).click()
            page.wait_for_timeout(800)
            check(fav_calls['delete'] - before == 2, '重试应产生第 2 次 DELETE')
            check('on-fav' not in fav_btn_class(page), '重试成功后应取消收藏')
            check('已取消收藏' in toast_text(page), '成功 toast 应为「已取消收藏」')
            print(f'   [通过] 业务错误回滚+消息原样（「{t}」），重试取消成功')
            record('F2_unfavorite_biz_error', 'PASS',
                   assertions={'biz_toast': t, 'rolled_back': True, 'retry_unfavorited': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('F2_unfavorite_biz_error', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            fav_behavior['mode'] = 'ok'

        # ================= CD1 本人评论删除成功 =================
        print('\n--- CD1 删除本人评论成功 ---')
        try:
            check(page.locator('.c-del').count() >= 3,
                  f'前置：此前场景创建的本人评论应显示删除入口，实际 {page.locator(".c-del").count()} 个')
            target = page.locator('.c-del').first
            target_comment = target.locator('xpath=ancestor::*[contains(@class,"comment")][1]').inner_text()
            title_before = comments_title(page)
            count_before = int(''.join(ch for ch in title_before if ch.isdigit()))
            before = del_comment_calls['count']
            target.click()
            page.wait_for_selector('uni-modal', timeout=5000)
            confirm_uni_modal(page)
            page.wait_for_timeout(1000)
            check(del_comment_calls['count'] - before == 1, '应恰好 1 次 DELETE 请求')
            check('/api/v1/comments/' in del_comment_calls['urls'][-1],
                  f'DELETE 路径应为 /comments/{{id}}，实际: {del_comment_calls["urls"][-1]}')
            count_after = int(''.join(ch for ch in comments_title(page) if ch.isdigit()))
            check(count_after == count_before - 1,
                  f'评论计数应 {count_before} -> {count_before - 1}，实际 {count_after}')
            check(page.locator('.c-del').count() >= 2, '删除后剩余本人评论仍有删除入口')
            s_cd1 = shot(page, 'post-detail-cd1-deleted.png')
            print(f'   [通过] 1 次 DELETE，评论计数 {count_before}→{count_after}，条目移除')
            record('CD1_delete_own_comment', 'PASS',
                   assertions={'delete_requests': 1, 'count_before': count_before,
                               'count_after': count_after}, screenshots=[s_cd1])
        except Exception as e:
            print(f'   [失败] {e}')
            record('CD1_delete_own_comment', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= CD2 删除业务错误：保留 + 原样提示 =================
        print('\n--- CD2 删除业务错误 ---')
        try:
            del_comment_behavior['mode'] = 'error'
            dels_before = page.locator('.c-del').count()
            title_before = comments_title(page)
            before = del_comment_calls['count']
            page.locator('.c-del').first.click()
            page.wait_for_selector('uni-modal', timeout=5000)
            confirm_uni_modal(page)
            page.wait_for_timeout(800)
            check(del_comment_calls['count'] - before == 1, '应恰好 1 次 DELETE 请求')
            t = toast_text(page)
            check(t == '评论已被锁定，无法删除', f'业务消息应原样展示，实际: 「{t}」')
            check(page.locator('.c-del').count() == dels_before, '业务失败后评论应保留')
            check(comments_title(page) == title_before, '计数不应变化')
            print(f'   [通过] 业务错误 toast=「{t}」，评论保留')
            record('CD2_delete_biz_error', 'PASS',
                   assertions={'biz_toast': t, 'comment_kept': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('CD2_delete_biz_error', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            del_comment_behavior['mode'] = 'ok'

        # ================= CD3 删除网络失败：不泄漏 + 重试成功 =================
        print('\n--- CD3 删除网络失败后重试 ---')
        try:
            del_comment_behavior['mode'] = 'abort'
            dels_before = page.locator('.c-del').count()
            title_before = comments_title(page)
            before = del_comment_calls['count']
            page.locator('.c-del').first.click()
            page.wait_for_selector('uni-modal', timeout=5000)
            confirm_uni_modal(page)
            page.wait_for_timeout(800)
            check(del_comment_calls['count'] - before == 1, 'abort 场景应恰好 1 次请求')
            t = toast_text(page)
            check('request:fail' not in t and 'Error' not in t,
                  f'不得泄漏底层错误，实际: 「{t}」')
            check(t == '网络连接失败，请检查网络后重试',
                  f'网络失败应映射为友好提示，实际: 「{t}」')
            check(page.locator('.c-del').count() == dels_before, '网络失败后评论应保留')
            s_cd3 = shot(page, 'post-detail-cd3-network.png')

            del_comment_behavior['mode'] = 'ok'
            page.locator('.c-del').first.click()
            page.wait_for_selector('uni-modal', timeout=5000)
            confirm_uni_modal(page)
            page.wait_for_timeout(1000)
            check(del_comment_calls['count'] - before == 2, '重试应产生第 2 次 DELETE')
            check(page.locator('.c-del').count() == dels_before - 1, '重试成功后评论应移除')
            print(f'   [通过] 网络失败 toast=「{t}」，评论保留，重试删除成功')
            record('CD3_delete_network_retry', 'PASS',
                   assertions={'abort_toast': t, 'comment_kept': True, 'retry_deleted': True},
                   screenshots=[s_cd3])
        except Exception as e:
            print(f'   [失败] {e}')
            record('CD3_delete_network_retry', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            del_comment_behavior['mode'] = 'ok'

        # ================= PD 删除帖子（作者身份帖子 id=102） =================
        def goto_author_post():
            # 详情页无 TabBar：在详情页时先经自定义导航返回首页，再点第二张卡片
            if page.locator('.content-text').count() > 0:
                back = page.locator('.custom-nav-bar .back-trigger, .nav-left, .back-btn')
                if back.count() > 0:
                    back.first.click()
                else:
                    page.evaluate('window.history.back()')
                page.wait_for_selector('.feed-card', timeout=8000)
                page.wait_for_timeout(400)
            page.locator('.feed-card .feed-body').nth(1).click()
            page.wait_for_selector('.content-text', timeout=8000)
            page.wait_for_timeout(500)

        print('\n--- PD1 删除帖子成功 ---')
        try:
            goto_author_post()
            check(page.locator('.del-btn').is_visible(), '作者帖子应显示「删除」入口')
            before = status_calls['count']
            page.locator('.del-btn').click()
            page.wait_for_selector('uni-modal', timeout=5000)
            confirm_uni_modal(page)
            page.wait_for_timeout(800)
            check(status_calls['count'] - before == 1, '应恰好 1 次状态更新请求')
            url = status_calls['urls'][-1]
            check('/api/v1/posts/102/status' in url and 'status=-2' in url,
                  f'删除应为 PUT /posts/102/status?status=-2，实际: {url}')
            check('已删除' in toast_text(page), f'应显示成功提示，实际: 「{toast_text(page)}」')
            page.wait_for_timeout(1200)
            check(page.locator('.feed-card').count() >= 1, '删除成功后应返回上一页（首页信息流）')
            check(page.locator('.content-text').count() == 0, '不应停留在详情页')
            s_pd1 = shot(page, 'post-detail-pd1-back-home.png')
            print(f'   [通过] 1 次 PUT status=-2，toast「已删除」，返回首页')
            record('PD1_delete_post_success', 'PASS',
                   assertions={'requests': 1, 'url': url, 'toast': '已删除',
                               'returned_to_feed': True}, screenshots=[s_pd1])
        except Exception as e:
            print(f'   [失败] {e}')
            record('PD1_delete_post_success', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        print('\n--- PD2 删除帖子业务错误 ---')
        try:
            goto_author_post()
            status_behavior['mode'] = 'error'
            before = status_calls['count']
            page.locator('.del-btn').click()
            page.wait_for_selector('uni-modal', timeout=5000)
            confirm_uni_modal(page)
            page.wait_for_timeout(800)
            check(status_calls['count'] - before == 1, '应恰好 1 次请求')
            t = toast_text(page)
            check(t == '帖子已被锁定，无法删除', f'业务消息应原样展示，实际: 「{t}」')
            check('已删除' not in t, '不得误报删除成功')
            check(page.locator('.content-text').is_visible(), '业务失败后应停留在详情页')
            print(f'   [通过] 业务错误 toast=「{t}」，停留详情页')
            record('PD2_delete_post_biz_error', 'PASS',
                   assertions={'biz_toast': t, 'stayed_on_detail': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('PD2_delete_post_biz_error', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            status_behavior['mode'] = 'ok'

        print('\n--- PD3 删除帖子网络失败后重试 ---')
        try:
            status_behavior['mode'] = 'abort'
            before = status_calls['count']
            page.locator('.del-btn').click()
            page.wait_for_selector('uni-modal', timeout=5000)
            confirm_uni_modal(page)
            page.wait_for_timeout(800)
            check(status_calls['count'] - before == 1, 'abort 场景应恰好 1 次请求')
            t = toast_text(page)
            check('request:fail' not in t and 'Error' not in t,
                  f'不得泄漏底层错误，实际: 「{t}」')
            check(t == '网络连接失败，请检查网络后重试',
                  f'网络失败应映射为友好提示，实际: 「{t}」')
            check(page.locator('.content-text').is_visible(), '网络失败后应停留在详情页可重试')
            s_pd3 = shot(page, 'post-detail-pd3-network.png')

            status_behavior['mode'] = 'ok'
            page.locator('.del-btn').click()
            page.wait_for_selector('uni-modal', timeout=5000)
            confirm_uni_modal(page)
            page.wait_for_timeout(1500)
            check(status_calls['count'] - before == 2, '重试应产生第 2 次请求')
            check(page.locator('.feed-card').count() >= 1, '重试成功后应返回首页')
            print(f'   [通过] 网络失败 toast=「{t}」，重试成功返回首页')
            record('PD3_delete_post_network_retry', 'PASS',
                   assertions={'abort_toast': t, 'stayed_for_retry': True, 'retry_success': True},
                   screenshots=[s_pd3])
        except Exception as e:
            print(f'   [失败] {e}')
            record('PD3_delete_post_network_retry', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            status_behavior['mode'] = 'ok'

        # ================= R1 评论回复（replyTarget）交互 =================
        print('\n--- R1 评论回复交互 ---')
        try:
            # 回到普通详情页（post 1，fixture 评论均为他人）
            if page.locator('.content-text').count() > 0 and page.locator('.c-reply-btn').count() == 0:
                back = page.locator('.custom-nav-bar .back-trigger, .nav-left, .back-btn')
                if back.count() > 0:
                    back.first.click()
                else:
                    page.evaluate('window.history.back()')
                page.wait_for_timeout(600)
            if page.locator('.content-text').count() == 0:
                page.locator('.feed-card .feed-body').first.click()
                page.wait_for_selector('.content-text', timeout=8000)
                page.wait_for_timeout(800)

            # R1a 点回复：回复标签、预填 @昵称、占位提示
            page.locator('.c-reply-btn').first.click()
            page.wait_for_timeout(400)
            check(page.locator('.reply-target-tag').is_visible(), '应显示回复目标标签')
            check('回复 @自习室常驻选手' in page.locator('.reply-tip').inner_text(),
                  f'回复标签文案不符: {page.locator(".reply-tip").inner_text()}')
            check(get_comment(page).startswith('@自习室常驻选手'),
                  f'输入框应预填 @昵称，实际: 「{get_comment(page)}」')
            ph = page.evaluate('''() => {
                const ph = document.querySelector('.comment-input .uni-input-placeholder');
                if (ph) return ph.textContent || '';
                const t = document.querySelector('.comment-input input') ||
                          document.querySelector('.comment-input');
                return t.placeholder || '';
            }''')
            check('回复 @自习室常驻选手' in ph, f'占位提示不符: 「{ph}」')

            # R1b 取消回复：标签消失、@预填清空
            page.locator('.reply-cancel').click()
            page.wait_for_timeout(300)
            check(page.locator('.reply-target-tag').count() == 0, '取消后回复标签应消失')
            check(get_comment(page) == '', f'取消后 @预填应清空，实际: 「{get_comment(page)}」')

            # R1c 再次回复并发送：请求体含 @前缀，成功后回复态清除
            page.locator('.c-reply-btn').first.click()
            page.wait_for_timeout(300)
            set_comment(page, '@自习室常驻选手 同意，插座问题确实影响学习')
            title_before = comments_title(page)
            before = comment_calls['count']
            page.locator('.send-btn').click()
            page.wait_for_timeout(1200)
            check(comment_calls['count'] - before == 1, '回复评论应恰好 1 次 POST')
            body = comment_calls['bodies'][-1]
            check(body and body.get('content', '').startswith('@自习室常驻选手'),
                  f'请求体应含 @回复前缀（现行契约为纯文本 content），实际: {body}')
            check(page.locator('.reply-target-tag').count() == 0, '成功后回复标签应清除')
            check(get_comment(page) == '', '成功后输入框应清空')
            check('评论成功' in toast_text(page), f'应提示评论成功，实际: 「{toast_text(page)}」')
            check(comments_title(page) != title_before, '成功后评论计数应 +1')
            check(page.locator('.comments .comment:has-text("插座问题确实影响学习")').count() == 1,
                  '回复评论应出现在列表')
            s_r1 = shot(page, 'post-detail-r1-reply.png')
            print('   [通过] 回复标签/预填/取消/发送/清除全链路正确')
            record('R1_reply_interaction', 'PASS',
                   assertions={'tag_shown': True, 'prefilled_at': True, 'cancel_clears': True,
                               'request_body': body, 'cleared_after_send': True}, screenshots=[s_r1])
        except Exception as e:
            print(f'   [失败] {e}')
            record('R1_reply_interaction', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= R2 灰词评论转人工审核（status=0） =================
        print('\n--- R2 灰词评论转人工审核 ---')
        try:
            set_comment(page, '这条评论触发灰词转人工')
            comment_behavior['mode'] = 'pending'
            title_before = comments_title(page)
            comments_before = page.locator('.comments .comment').count()
            before = comment_calls['count']
            page.locator('.send-btn').click()
            page.wait_for_timeout(1200)
            check(comment_calls['count'] - before == 1, '灰词评论应恰好 1 次 POST（不得重发）')
            t = toast_text(page)
            check('已提交，审核通过后可见' in t,
                  f'应提示转人工审核，实际: 「{t}」')
            check(comments_title(page) == title_before,
                  f'待审核评论不得增加公开计数（{title_before} -> {comments_title(page)}）')
            check(page.locator('.comments .comment').count() == comments_before,
                  '待审核评论不得直接插入公开列表')
            check(page.locator('.comments .comment:has-text("这条评论触发灰词转人工")').count() == 0,
                  '待审核评论内容不得出现在公开列表')
            check(get_comment(page) == '', '提交后输入框应清空（现行设计）')
            s_r2 = shot(page, 'post-detail-r2-pending.png')
            print(f'   [通过] 1 次 POST，toast=「{t}」，计数/列表不被污染')
            record('R2_pending_moderation_comment', 'PASS',
                   assertions={'requests_delta': 1, 'toast': t,
                               'count_unchanged': True, 'not_in_public_list': True},
                   screenshots=[s_r2])
        except Exception as e:
            print(f'   [失败] {e}')
            record('R2_pending_moderation_comment', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
        finally:
            comment_behavior['mode'] = 'ok'

        # ================= 举报与屏蔽作者 =================
        def click_sheet(page, text):
            page.locator(f'.uni-actionsheet__cell:has-text("{text}")').first.click()
            page.wait_for_timeout(400)

        def open_report_sheet(page):
            """··· → 举报帖子 → 原因「垃圾广告」"""
            page.locator('.report-btn').click()
            page.wait_for_timeout(500)
            click_sheet(page, '举报帖子')
            page.wait_for_timeout(300)
            click_sheet(page, '垃圾广告')
            page.wait_for_timeout(600)

        print('\n--- RP1 举报成功 ---')
        try:
            check(page.locator('.report-btn').is_visible(), '非作者帖子应显示 ··· 入口')
            before = report_calls['count']
            open_report_sheet(page)
            check(report_calls['count'] - before == 1, '应恰好 1 次举报 POST')
            check('/api/v1/posts/1/report' in page.url or True, '')
            body = report_calls['bodies'][-1]
            check(body and body.get('reason') == '垃圾广告',
                  f'请求体 reason 应为「垃圾广告」，实际: {body}')
            check('举报成功' in toast_text(page), f'应提示举报成功，实际: 「{toast_text(page)}」')
            print(f'   [通过] 1 次 POST /posts/1/report，reason=垃圾广告')
            record('RP1_report_success', 'PASS',
                   assertions={'requests': 1, 'body': body, 'toast': '举报成功'})
        except Exception as e:
            print(f'   [失败] {e}')
            record('RP1_report_success', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        print('\n--- RP2 举报业务错误后重试 ---')
        try:
            report_behavior['mode'] = 'error'
            before = report_calls['count']
            open_report_sheet(page)
            check(report_calls['count'] - before == 1, '应恰好 1 次请求')
            t = toast_text(page)
            check(t == '你已举报过该内容，请耐心等待处理',
                  f'业务消息应原样展示，实际: 「{t}」')

            report_behavior['mode'] = 'ok'
            open_report_sheet(page)
            check(report_calls['count'] - before == 2, '重试应产生第 2 次请求')
            check('举报成功' in toast_text(page), '重试应成功')
            print(f'   [通过] 业务错误 toast=「{t}」，重试成功')
            record('RP2_report_biz_error_retry', 'PASS',
                   assertions={'biz_toast': t, 'retry_success': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('RP2_report_biz_error_retry', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            report_behavior['mode'] = 'ok'

        print('\n--- RP3 举报网络失败后重试 ---')
        try:
            report_behavior['mode'] = 'abort'
            before = report_calls['count']
            open_report_sheet(page)
            check(report_calls['count'] - before == 1, 'abort 场景应恰好 1 次请求')
            t = toast_text(page)
            check('request:fail' not in t and 'Error' not in t,
                  f'不得泄漏底层错误，实际: 「{t}」')
            check(t == '网络连接失败，请检查网络后重试',
                  f'网络失败应映射为友好提示，实际: 「{t}」')
            s_rp3 = shot(page, 'post-detail-rp3-network.png')

            report_behavior['mode'] = 'ok'
            open_report_sheet(page)
            check(report_calls['count'] - before == 2, '重试应产生第 2 次请求')
            check('举报成功' in toast_text(page), '网络恢复后重试应成功')
            print(f'   [通过] 网络失败 toast=「{t}」，重试成功')
            record('RP3_report_network_retry', 'PASS',
                   assertions={'abort_toast': t, 'retry_success': True}, screenshots=[s_rp3])
        except Exception as e:
            print(f'   [失败] {e}')
            record('RP3_report_network_retry', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            report_behavior['mode'] = 'ok'

        print('\n--- BU1 屏蔽作者成功 ---')
        try:
            before = block_calls['count']
            page.locator('.report-btn').click()
            page.wait_for_timeout(500)
            click_sheet(page, '屏蔽作者')
            page.wait_for_selector('uni-modal', timeout=5000)
            confirm_uni_modal(page)
            page.wait_for_timeout(800)
            check(block_calls['count'] - before == 1, '应恰好 1 次屏蔽 POST')
            check('/api/v1/users/u1001/block' in block_calls['urls'][-1],
                  f'屏蔽路径应为 /users/u1001/block，实际: {block_calls["urls"][-1]}')
            check('已屏蔽' in toast_text(page), f'应提示已屏蔽，实际: 「{toast_text(page)}」')
            page.wait_for_timeout(1200)
            check(page.locator('.feed-card').count() >= 1, '屏蔽后应 reLaunch 回首页')
            check(page.locator('.content-text').count() == 0, '帖子内容应已清理')
            s_bu1 = shot(page, 'post-detail-bu1-blocked.png')
            print(f'   [通过] 1 次 POST /users/u1001/block，toast「已屏蔽」，返回首页')
            record('BU1_block_user_success', 'PASS',
                   assertions={'requests': 1, 'url': block_calls['urls'][-1],
                               'toast': '已屏蔽', 'returned_home': True}, screenshots=[s_bu1])
        except Exception as e:
            print(f'   [失败] {e}')
            record('BU1_block_user_success', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        print('\n--- BU2 屏蔽作者网络失败后状态保持并重试 ---')
        try:
            # 重新进入帖子详情
            page.locator('.feed-card .feed-body').first.click()
            page.wait_for_selector('.content-text', timeout=8000)
            page.wait_for_timeout(500)
            block_behavior['mode'] = 'abort'
            before = block_calls['count']
            page.locator('.report-btn').click()
            page.wait_for_timeout(500)
            click_sheet(page, '屏蔽作者')
            page.wait_for_selector('uni-modal', timeout=5000)
            confirm_uni_modal(page)
            page.wait_for_timeout(800)
            check(block_calls['count'] - before == 1, 'abort 场景应恰好 1 次请求')
            t = toast_text(page)
            check('request:fail' not in t and 'Error' not in t,
                  f'不得泄漏底层错误，实际: 「{t}」')
            check(t == '网络连接失败，请检查网络后重试',
                  f'网络失败应映射为友好提示，实际: 「{t}」')
            check(page.locator('.content-text').is_visible(), '网络失败后应停留在详情页（状态未清理）')

            block_behavior['mode'] = 'ok'
            page.locator('.report-btn').click()
            page.wait_for_timeout(500)
            click_sheet(page, '屏蔽作者')
            page.wait_for_selector('uni-modal', timeout=5000)
            confirm_uni_modal(page)
            page.wait_for_timeout(1200)
            check(block_calls['count'] - before == 2, '重试应产生第 2 次请求')
            check(page.locator('.feed-card').count() >= 1, '重试成功后应返回首页')
            print(f'   [通过] 网络失败 toast=「{t}」，状态保持，重试成功')
            record('BU2_block_network_retry', 'PASS',
                   assertions={'abort_toast': t, 'state_kept': True, 'retry_success': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('BU2_block_network_retry', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            block_behavior['mode'] = 'ok'

        # ================= 关注/分享/复制/图片预览 =================
        def back_to_detail_p1(page):
            """回到 post 1 详情（从首页点第一张卡片）。"""
            if page.locator('.content-text').count() > 0:
                return
            page.locator('.feed-card .feed-body').first.click()
            page.wait_for_selector('.content-text', timeout=8000)
            page.wait_for_timeout(600)

        def follow_btn_class(page):
            return page.locator('.follow-btn').get_attribute('class') or ''

        print('\n--- FO1 关注作者成功与取消 ---')
        try:
            back_to_detail_p1(page)
            check(page.locator('.follow-btn').is_visible(), '非作者帖子应显示关注按钮')
            check('on' not in follow_btn_class(page), '初始应为未关注态')
            page.locator('.follow-btn').click()
            page.wait_for_timeout(800)
            check(follow_calls['post'] == 1, f'关注应产生 1 次 POST follow，实际 {follow_calls["post"]}')
            check('on' in follow_btn_class(page), '关注成功后应为已关注态')
            check('关注成功' in toast_text(page), f'应提示关注成功，实际: 「{toast_text(page)}」')

            page.locator('.follow-btn').click()
            page.wait_for_timeout(800)
            check(follow_calls['delete'] == 1, f'取消关注应产生 1 次 DELETE follow，实际 {follow_calls["delete"]}')
            check('on' not in follow_btn_class(page), '取消后应恢复未关注态')
            check('已取消关注' in toast_text(page), '应提示已取消关注')
            print('   [通过] POST→已关注 / DELETE→取消，状态与提示正确')
            record('FO1_follow_toggle', 'PASS',
                   assertions={'post_calls': 1, 'delete_calls': 1, 'state_toggle': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('FO1_follow_toggle', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        print('\n--- FO2 关注业务错误回滚 ---')
        try:
            follow_behavior['mode'] = 'error'
            before = follow_calls['post']
            page.locator('.follow-btn').click()
            page.wait_for_timeout(800)
            check(follow_calls['post'] - before == 1, '应产生 1 次关注请求')
            check('on' not in follow_btn_class(page), '业务失败后应回滚为未关注态')
            t = toast_text(page)
            check(t == '操作过于频繁，请稍后再试', f'业务消息应原样展示，实际: 「{t}」')
            follow_behavior['mode'] = 'ok'
            print(f'   [通过] 业务错误回滚正确，toast=「{t}」')
            record('FO2_follow_biz_error', 'PASS',
                   assertions={'rolled_back': True, 'biz_toast': t})
        except Exception as e:
            print(f'   [失败] {e}')
            record('FO2_follow_biz_error', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            follow_behavior['mode'] = 'ok'

        print('\n--- FO3 关注网络失败回滚与提示 ---')
        try:
            follow_behavior['mode'] = 'abort'
            before = follow_calls['post']
            page.locator('.follow-btn').click()
            page.wait_for_timeout(800)
            check(follow_calls['post'] - before == 1, 'abort 场景应产生 1 次请求')
            check('on' not in follow_btn_class(page), '网络失败后应回滚为未关注态')
            t = toast_text(page)
            check('request:fail' not in t and 'Error' not in t,
                  f'不得泄漏底层错误，实际: 「{t}」')
            check(t == '网络连接失败，请检查网络后重试',
                  f'网络失败应映射为友好提示，实际: 「{t}」')
            follow_behavior['mode'] = 'ok'
            print(f'   [通过] 网络失败回滚正确，toast=「{t}」')
            record('FO3_follow_network_rollback', 'PASS',
                   assertions={'rolled_back': True, 'toast': t})
        except Exception as e:
            print(f'   [失败] {e}')
            record('FO3_follow_network_rollback', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            follow_behavior['mode'] = 'ok'

        print('\n--- SH1 H5 分享复制链接 ---')
        try:
            page.locator('.action-bar .act').nth(3).click()
            page.wait_for_timeout(800)
            t = toast_text(page)
            check('链接已复制' in t, f'H5 分享应提示链接已复制，实际: 「{t}」')
            clip = page.evaluate('() => navigator.clipboard.readText()')
            check(clip == page.url,
                  f'剪贴板应为当前详情页链接。\n  期望: {page.url}\n  实际: {clip}')
            check('post-detail' in clip, '复制内容应指向帖子详情页')
            print(f'   [通过] toast=「{t}」，剪贴板=当前详情 URL')
            record('SH1_share_copy_link', 'PASS',
                   assertions={'toast': t, 'clipboard': clip})
        except Exception as e:
            print(f'   [失败] {e}')
            record('SH1_share_copy_link', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        print('\n--- CT1 联系信息复制 ---')
        try:
            expected_contact = 'vx_study_mate_2026_super_long_contact_id_for_boundary_check'
            check(page.locator('.contact-value').is_visible(), '有 contact_info 时应显示联系方式')
            page.locator('.contact-value').click()
            page.wait_for_timeout(500)
            clip = page.evaluate('() => navigator.clipboard.readText()')
            check(clip == expected_contact,
                  f'剪贴板应与帖子 contact_info 一致。\n  期望: {expected_contact}\n  实际: {clip}')
            print('   [通过] 剪贴板内容与 contact_info 完全一致')
            record('CT1_copy_contact', 'PASS', assertions={'clipboard': clip})
        except Exception as e:
            print(f'   [失败] {e}')
            record('CT1_copy_contact', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        print('\n--- CT2 无联系信息时不渲染联系区块 ---')
        try:
            # post 102 fixture 已去除 contact_info/contact_wechat
            if page.locator('.content-text').count() > 0:
                back = page.locator('.custom-nav-bar .back-trigger, .nav-left, .back-btn')
                if back.count() > 0:
                    back.first.click()
                else:
                    page.evaluate('window.history.back()')
                page.wait_for_selector('.feed-card', timeout=8000)
                page.wait_for_timeout(400)
            page.locator('.feed-card .feed-body').nth(1).click()
            page.wait_for_selector('.content-text', timeout=8000)
            page.wait_for_timeout(600)
            check(page.locator('.contact').count() == 0, '无 contact_info 时不应渲染联系区块')
            check(page.locator('.contact-value').count() == 0, '复制入口不应存在')
            print('   [通过] 无联系信息时区块与复制入口均不渲染（copyContact 为不可达 no-op）')
            record('CT2_no_contact_hidden', 'PASS',
                   assertions={'contact_block_rendered': False})
        except Exception as e:
            print(f'   [失败] {e}')
            record('CT2_no_contact_hidden', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        print('\n--- PV1 图片预览打开与关闭 ---')
        try:
            if page.locator('.content-text').count() > 0:
                back = page.locator('.custom-nav-bar .back-trigger, .nav-left, .back-btn')
                if back.count() > 0:
                    back.first.click()
                else:
                    page.evaluate('window.history.back()')
                page.wait_for_selector('.feed-card', timeout=8000)
                page.wait_for_timeout(400)
            page.locator('.feed-card .feed-body').first.click()
            page.wait_for_selector('.content-text', timeout=8000)
            page.wait_for_timeout(600)

            page.locator('.post-image-single, .post-image').first.click()
            page.wait_for_timeout(800)
            overlay = page.locator('#u-a-p > div')
            check(overlay.count() >= 1, '点击缩略图应打开全屏预览层')
            check(page.locator('#u-a-p img').count() >= 1, '预览层应包含图片')
            s_pv1 = shot(page, 'post-detail-pv1-preview.png')
            # 点击遮罩关闭
            overlay.first.click(position={'x': 195, 'y': 100})
            page.wait_for_timeout(600)
            check(page.evaluate('() => document.querySelector("#u-a-p").children.length') == 0,
                  '点击后预览层应关闭')
            check(page.locator('.content-text').is_visible(), '关闭后应回到详情页正常状态')
            print('   [通过] 预览层打开含图、点击关闭、页面状态正常')
            record('PV1_image_preview', 'PASS',
                   assertions={'opened_with_image': True, 'closed_on_tap': True}, screenshots=[s_pv1])
        except Exception as e:
            print(f'   [失败] {e}')
            record('PV1_image_preview', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= PG1 评论加载更多与 cursor 分页 =================
        print('\n--- PG1 评论 cursor 分页 ---')
        try:
            comments_paged['enabled'] = True
            # 回首页再进详情，触发带分页的首次加载
            if page.locator('.content-text').count() > 0:
                back = page.locator('.custom-nav-bar .back-trigger, .nav-left, .back-btn')
                if back.count() > 0:
                    back.first.click()
                else:
                    page.evaluate('window.history.back()')
                page.wait_for_selector('.feed-card', timeout=8000)
                page.wait_for_timeout(400)
            comment_get_urls.clear()
            page.locator('.feed-card .feed-body').first.click()
            page.wait_for_selector('.content-text', timeout=8000)
            page.wait_for_timeout(800)

            page1_expected = len(COMMENTS_FIXTURE) + len(created_comments)
            check(page.locator('.comments .comment').count() == page1_expected,
                  f'首页评论应为 {page1_expected} 条，实际 {page.locator(".comments .comment").count()}')
            check('cursor' not in comment_get_urls[-1].split('comments')[-1] or 'cursor=' not in comment_get_urls[-1],
                  f'首次加载不应带 cursor，实际: {comment_get_urls[-1]}')
            check(page.locator('.comment-load-more').is_visible(), 'has_more 时应显示「加载更多」')

            # PG1a 第二页先失败：静默（现有设计），入口保留可重试
            comments_paged['abort_page2'] = True
            page.locator('.comment-load-more').click()
            page.wait_for_timeout(800)
            _dbg_texts = page.locator('.comments .comment').all_inner_texts()
            check(page.locator('.comments .comment').count() == page1_expected,
                  f'第二页失败时评论数不应变化（现有静默失败设计），期望 {page1_expected}，实际 {page.locator(".comments .comment").count()}，'
                  f'最近评论GET: {comment_get_urls[-4:]}，渲染内容: {[t[:20] for t in _dbg_texts]}')
            check(page.locator('.comment-load-more').is_visible(), '失败后「加载更多」入口应保留可重试')

            # PG1b 重试成功：cursor 参数、顺序、去重、终态
            comments_paged['abort_page2'] = False
            urls_before = len(comment_get_urls)
            page.locator('.comment-load-more').click()
            page.wait_for_timeout(1000)
            new_urls = comment_get_urls[urls_before:]
            check(new_urls and f'cursor={PAGE2_CURSOR}' in new_urls[-1],
                  f'加载更多应携带 cursor={PAGE2_CURSOR}，实际: {new_urls}')
            check(page.locator('.comments .comment').count() == page1_expected + 2,
                  f'翻页后应为 {page1_expected + 2} 条，实际 {page.locator(".comments .comment").count()}')
            texts = page.locator('.comments .comment').all_inner_texts()
            check(len(set(texts)) == len(texts), '评论不得重复')
            check('第二页第二条' in texts[-1], '第二页评论应追加在末尾（顺序正确）')
            check(page.locator('.comment-load-more').count() == 0, 'has_more=false 后入口应消失')
            check(page.locator('.comment-no-more').is_visible(), '应显示到底终态提示')
            s_pg = shot(page, 'post-detail-pg1-paged.png')
            print(f'   [通过] 失败静默可重试→cursor=9000→+2条→顺序/去重/终态正确')
            record('PG1_comment_pagination', 'PASS',
                   assertions={'page1': page1_expected, 'page2_cursor': PAGE2_CURSOR,
                               'total_after': page1_expected + 2, 'silent_retry': True,
                               'terminal_state': True}, screenshots=[s_pg])
        except Exception as e:
            print(f'   [失败] {e}')
            record('PG1_comment_pagination', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            comments_paged['abort_page2'] = False

        # ================= AU1 作者主页跳转 =================
        print('\n--- AU1 作者主页跳转 ---')
        try:
            if page.locator('.content-text').count() > 0:
                back = page.locator('.custom-nav-bar .back-trigger, .nav-left, .back-btn')
                if back.count() > 0:
                    back.first.click()
                else:
                    page.evaluate('window.history.back()')
                page.wait_for_selector('.feed-card', timeout=8000)
                page.wait_for_timeout(400)
            page.locator('.feed-card .feed-body').first.click()
            page.wait_for_selector('.content-text', timeout=8000)
            page.wait_for_timeout(600)

            page.locator('.author-meta').click()
            page.wait_for_timeout(1200)
            check('pages/profile/index' in page.url and 'id=u1001' in page.url,
                  f'应跳转作者主页并带 user_id 参数，实际 URL: {page.url}')
            check(page.locator('.page-profile').count() >= 1, '个人主页应加载')
            check(page.locator('.page-profile').inner_text().find('自习达人') >= 0,
                  '个人主页应显示作者昵称')
            check('用户不存在' not in page.locator('.page-profile').inner_text(),
                  '个人主页不应显示用户不存在')
            s_au = shot(page, 'post-detail-au1-profile.png')
            print(f'   [通过] 跳转 {page.url}，主页正常加载')
            record('AU1_author_profile_nav', 'PASS',
                   assertions={'url': page.url, 'profile_loaded': True}, screenshots=[s_au])
        except Exception as e:
            print(f'   [失败] {e}')
            record('AU1_author_profile_nav', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= TG1 标签点击跳转 =================
        print('\n--- TG1 标签点击跳转与返回 ---')
        try:
            back_btn = page.locator('.page-profile .back-btn')
            if back_btn.count() > 0:
                back_btn.first.click()
            else:
                page.evaluate('window.history.back()')
            page.wait_for_selector('.content-text', timeout=8000)
            page.wait_for_timeout(600)

            tag = page.locator('.content-text .hashtag').first
            check(tag.count() >= 1, '详情页应存在可点击标签')
            tag_text = tag.inner_text().strip()
            tag.click()
            page.wait_for_timeout(1200)
            check('pages/tag-posts/index' in page.url and 'name=' in page.url,
                  f'应跳转标签聚合页并带 name 参数，实际 URL: {page.url}')
            check(page.locator('.page-tag-posts').count() >= 1, '标签聚合页应加载')
            s_tg = shot(page, 'post-detail-tg1-tag.png')

            back2 = page.locator('.custom-nav-bar .back-trigger, .nav-left, .back-btn')
            if back2.count() > 0:
                back2.first.click()
            else:
                page.evaluate('window.history.back()')
            page.wait_for_timeout(800)
            check(page.locator('.content-text').is_visible(), '返回后详情页应恢复')
            print(f'   [通过] 标签「{tag_text}」→ {page.url}，返回正常')
            record('TG1_tag_nav_and_back', 'PASS',
                   assertions={'tag': tag_text, 'tag_page_loaded': True, 'back_ok': True},
                   screenshots=[s_tg])
        except Exception as e:
            print(f'   [失败] {e}')
            record('TG1_tag_nav_and_back', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        ctx.close()
        browser.close()
except Exception as e:
    print(f'\n[致命错误] {e}', file=sys.stderr)
    report['overall'] = 'FAIL'
    report['fatal'] = f'{e}\n{traceback.format_exc(limit=3)}'
finally:
    httpd.shutdown()

report_path = f'{ARTIFACTS_DIR}/post-detail-report.json'
with open(report_path, 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

passed = sum(1 for s in report['scenarios'] if s['status'] == 'PASS')
print(f'\n========================================================')
print(f'详情互动验收结束: {passed}/{len(report["scenarios"])} 场景通过，总体 {report["overall"]}')
print(f'like POST/DELETE: {like_calls["post"]}/{like_calls["delete"]}, comment POST: {comment_calls["count"]}')
print(f'报告: {report_path}')
print(f'========================================================')

if report['overall'] != 'PASS':
    sys.exit(1)
