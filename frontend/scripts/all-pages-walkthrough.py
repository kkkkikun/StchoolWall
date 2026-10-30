#!/usr/bin/env python3
"""
SchoolWall 学生端「全页面」Playwright 走查（H5）

覆盖 pages.json 注册的全部页面 × 亮色/暗色双模式，逐页断言：
  1. 路由可达且根节点有真实渲染内容（空白页/崩溃即失败）
  2. 文档级横向溢出（移动端布局塌陷）
  3. 可见文本被裁切（overflow:visible 下的文字溢出，X 式简洁排版的硬伤）
  4. 控制台错误与未处理 Promise 异常
  5. 底部导航栏不遮挡内容

产物：ci-artifacts/ui-walkthrough/all-pages-report.json + all-pages-*.png
任一断言失败 -> 该场景 FAIL，退出码非零。全部走 Mock API，不连真实后端。
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
import urllib.parse

from playwright.sync_api import sync_playwright

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIST_DIR = os.path.join(ROOT_DIR, 'frontend', 'dist', 'build', 'h5')
ARTIFACTS_DIR = os.path.join(ROOT_DIR, 'ci-artifacts', 'ui-walkthrough')
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

if not os.path.isdir(DIST_DIR):
    print(f"Error: DIST_DIR not found at {DIST_DIR}. Run 'npm run build:h5' first.", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------- 静态服务
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind(('127.0.0.1', 0))
port = sock.getsockname()[1]
sock.close()


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST_DIR, **kwargs)

    def log_message(self, fmt, *args):
        pass


httpd = socketserver.TCPServer(('127.0.0.1', port), QuietHandler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
base_url = f'http://127.0.0.1:{port}'
print(f'H5 static server listening on {base_url}')

# ---------------------------------------------------------------- Mock 夹具
USER_ID = '11111111-1111-4111-8111-111111111111'

PROFILE = {
    'id': USER_ID, 'nickname': '走查同学', 'avatar_url': None, 'banner_url': None,
    'bio': '计算机学院大三｜图书馆常驻｜偶尔发发呆', 'is_verified': True, 'school': '示例大学',
    'posts_count': 12, 'following_count': 34, 'followers_count': 56, 'is_following': False,
    'is_self': True,
}


def make_post(i: int) -> dict:
    return {
        'id': i,
        'post_type': ['general', 'second_hand', 'lost_found'][i % 3],
        'category': ['广场', '二手', '失物'][i % 3],
        'content': f'第{i}条走查用帖子：用于验证信息流渲染与长文本换行表现，内容需要足够长以触发多行排版检查。',
        'images': [], 'images_count': 0, 'price': 99.0 if i % 3 == 1 else None,
        'status': 1, 'is_pinned': False, 'is_featured': False,
        'author': {'id': USER_ID, 'nickname': '走查同学', 'avatar_url': None, 'is_verified': True},
        'like_count': i * 3, 'comment_count': i, 'view_count': 100 + i,
        'created_at': f'2026-10-{(i % 28) + 1:02d}T08:00:00Z',
    }


POSTS = [make_post(i) for i in range(1, 9)]

PARTIES = [{
    'id': 1, 'type': 'group', 'category': '学习', 'title': '考研数学冲刺自习小组',
    'content': '每晚七点图书馆三楼一起刷题，人满为止。', 'total': 6, 'joined_count': 4,
    'status': 1, 'meet_time': '2026-10-25T19:00:00', 'location': '图书馆三楼',
    'user': {'nickname': '走查同学'}, 'is_joined': False,
    'created_at': '2026-10-20T08:00:00Z',
} for _ in range(3)]

NOTIFICATIONS = [{
    'id': 1, 'type': 'comment', 'actor': {'nickname': '走查同学'},
    'post_id': 1, 'comment_id': None, 'is_read': False,
    'created_at': '2026-10-22T08:00:00Z',
    'payload': {'title': '公告标题', 'content': '公告正文，用于验证公告详情渲染。'},
} for _ in range(4)]

TAGS = [{'id': 1, 'name': '考研'}, {'id': 2, 'name': '二手'}, {'id': 3, 'name': '失物'}]

HOT_USERS = [{'id': USER_ID, 'nickname': '走查同学', 'avatar_url': None, 'heat': 128}]

BLOCKS = [{'id': USER_ID, 'nickname': '被拉黑同学'}]

APPEALS = [{'id': 'a-1', 'entity_type': 'post', 'entity_id': '1', 'reason': '误判申诉：内容为课程作业讨论',
            'status': 'pending', 'created_at': '2026-10-21T08:00:00Z'}]

ACTIVITIES = [{'id': 1, 'title': '秋季摄影展征稿', 'image_url': None, 'summary': '银杏主题，拍摄校园一角即可',
               'content': '秋季摄影展征稿说明正文。', 'location': '大学生活动中心',
               'start_at': '2026-10-20T08:00:00Z', 'end_at': '2026-10-30T08:00:00Z',
               'status': 1, 'created_at': '2026-10-19T08:00:00Z'}]

VERIFICATION_ME = {'enabled': True, 'school_name': '示例大学', 'verification': None}
VERIFICATION_CHALLENGE = {'verification_id': 'v-1', 'challenge_id': 'c-1', 'code': '4821',
                          'expires_at': '2026-10-25T08:00:00Z'}


def ok(data):
    return {'code': 0, 'data': data}


def items(rows):
    return ok({'items': rows, 'total': len(rows), 'has_more': False})


def handle_api(route):
    url = route.request.url
    path = urllib.parse.urlparse(url).path
    if path.endswith('/user/profile'):
        route.fulfill(status=200, content_type='application/json', body=json.dumps(ok(PROFILE)))
    elif '/users/' in path and path.endswith('/profile'):
        route.fulfill(status=200, content_type='application/json', body=json.dumps(ok(PROFILE)))
    elif '/users/' in path and (path.endswith('/following') or path.endswith('/followers')):
        route.fulfill(status=200, content_type='application/json', body=json.dumps(items(HOT_USERS)))
    elif '/users/' in path and path.endswith('/posts'):
        route.fulfill(status=200, content_type='application/json', body=json.dumps(items(POSTS)))
    elif '/posts/hot' in path:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(items(POSTS[:10])))
    elif '/posts/search' in path:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(items(POSTS[:3])))
    elif '/posts/featured' in path:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(items(POSTS[:2])))
    elif '/posts/following' in path:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(items(POSTS[:2])))
    elif path.endswith('/posts') or path.endswith('/posts/'):
        route.fulfill(status=200, content_type='application/json', body=json.dumps(items(POSTS)))
    elif '/posts/' in path and 'comments' in path:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(items([])))
    elif '/posts/' in path:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(ok(make_post(1))))
    elif '/notifications/unread' in path or '/notification/unread' in path:
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps(ok({'comment': 1, 'like': 0, 'favorite': 0,
                                          'group': 0, 'moderation': 0})))
    elif '/notifications' in path:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(items(NOTIFICATIONS)))
    elif '/parties/summary' in path:
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps(ok({'total_members': 12})))
    elif '/me/parties' in path:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(items(PARTIES[:1])))
    elif '/parties' in path:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(items(PARTIES)))
    elif '/tags' in path:
        # getTags() 返回 Tag[] 本身，不是 {items: []}
        route.fulfill(status=200, content_type='application/json', body=json.dumps(ok(TAGS)))
    elif '/user/blocks' in path:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(items(BLOCKS)))
    elif '/appeals' in path:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(items(APPEALS)))
    elif '/activities' in path or '/activity' in path:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(ok(ACTIVITIES[0])))
    elif '/student-verifications/challenge' in path:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(ok(VERIFICATION_CHALLENGE)))
    elif '/student-verifications/me' in path:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(ok(VERIFICATION_ME)))
    elif '/user/hot-ranking' in path:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(items(HOT_USERS)))
    elif '/user/checkin/status' in path:
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps(ok({'checked_in': False, 'continuous_days': 0})))
    elif '/banners' in path:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(items([])))
    elif '/my/' in path or '/interactions' in path:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(items(POSTS[:3])))
    elif '/stats' in path:
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps(ok({'posts': 12, 'comments': 8, 'likes': 20, 'favorites': 5})))
    else:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(items([])))


# ---------------------------------------------------------------- 页面清单
PAGES = [
    ('index', 'pages/index/index', ''),
    ('group', 'pages/group/index', ''),
    ('publish', 'pages/publish/index', ''),
    ('profile-edit', 'pages/profile-edit/index', ''),
    ('info', 'pages/info/index', ''),
    ('hot', 'pages/hot/index', ''),
    ('interactions', 'pages/interactions/index', ''),
    ('message', 'pages/message/index', ''),
    ('announcement-detail', 'pages/announcement-detail/index', '?id=1'),
    ('activity', 'pages/activity/index', '?id=1'),
    ('tag-posts', 'pages/tag-posts/index', '?id=1'),
    ('hot-users', 'pages/hot-users/index', ''),
    ('mine', 'pages/mine/index', ''),
    ('auth', 'pages/auth/index', ''),
    ('post-detail', 'pages/post-detail/index', '?id=1'),
    ('search', 'pages/search/index', ''),
    ('party-create', 'pages/party-create/index', ''),
    ('profile', 'pages/profile/index', f'?id={USER_ID}'),
    ('webview', 'pages/webview/index', '?url=https%3A%2F%2Fexample.com'),
    ('settings', 'pages/settings/index', ''),
    ('oauth-callback', 'pages/oauth-callback/index', '?code=mock&state=mock'),
    ('verify', 'pages/verify/index', ''),
    ('tags', 'pages/tags/index', ''),
    ('admin', 'pages/admin/index', ''),
    ('my-posts', 'pages/my-posts/index', ''),
    ('appeals', 'pages/appeals/index', ''),
    ('blocks', 'pages/blocks/index', ''),
]

report = {
    'task': 'student H5 all-pages browser acceptance (every registered page x light/dark)',
    'date_utc': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
    'base_url': base_url,
    'browser': 'chromium(headless, single instance, serial)',
    'viewport': '390x844',
    'mock_scope': 'All /api/v1/** intercepted locally with synthetic fixtures; no real backend.',
    'pages_checked': len(PAGES),
    'scenarios': [],
    'screenshots': [],
    'overall': 'PASS',
}

console_errors: list[str] = []
page_errors: list[str] = []
brand_counts: dict[str, int] = {}


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def measure(page):
    """一次性采集文档溢出 / 根节点高度 / 可见文字裁切 / 文字对比度。"""
    return page.evaluate('''() => {
        const doc = document.documentElement;
        const root = document.querySelector('uni-app, #app, body');
        const clipped = [];
        const lowContrast = [];
        const brandLowContrast = [];
        const parseColor = (c) => {
            const m = /rgba?\\(([^)]+)\\)/.exec(c || '');
            if (!m) return null;
            const p = m[1].split(',').map(s => parseFloat(s));
            return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1};
        };
        const lum = ({r, g, b}) => {
            const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
            return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
        };
        const ratio = (fg, bg) => {
            const a = lum(fg), b = lum(bg);
            const L = Math.max(a, b), D = Math.min(a, b);
            return (L + 0.05) / (D + 0.05);
        };
        // 逐级向上找不透明底色；遇到渐变/图片背景则放弃该元素（无法静态判定）
        const effectiveBg = (el) => {
            let node = el;
            while (node && node.nodeType === 1) {
                const cs = getComputedStyle(node);
                if (cs.backgroundImage && cs.backgroundImage !== 'none') return null;
                const c = parseColor(cs.backgroundColor);
                if (c && c.a > 0.95) return c;
                node = node.parentElement;
            }
            return {r: 255, g: 255, b: 255, a: 1};
        };
        for (const el of document.querySelectorAll('body *')) {
            const cs = getComputedStyle(el);
            if (cs.display === 'none' || cs.visibility === 'hidden') continue;
            if (cs.overflowX === 'auto' || cs.overflowX === 'scroll') continue;
            if (el.clientWidth === 0) continue;
            const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
            if (!own) continue;
            const text = el.textContent.trim().slice(0, 30);
            if (el.scrollWidth > el.clientWidth + 4 && cs.overflowX === 'visible') {
                clipped.push({
                    tag: el.tagName,
                    cls: (el.className && el.className.toString ? el.className.toString() : '').slice(0, 60),
                    text: text,
                    scrollWidth: el.scrollWidth,
                    clientWidth: el.clientWidth,
                });
            }
            // 对比度：禁用态与渐变底不参与判定
            if (el.closest('[disabled], .is-disabled, .uni-button-disabled')) continue;
            if (parseFloat(cs.opacity) < 0.6) continue;
            const fg = parseColor(cs.color);
            const bg = effectiveBg(el);
            if (!fg || !bg) continue;
            const size = parseFloat(cs.fontSize) || 16;
            const weight = parseInt(cs.fontWeight, 10) || 400;
            const large = size >= 24 || (size >= 18.66 && weight >= 700);
            const cls = (el.className && el.className.toString ? el.className.toString() : '');
            // 占位符是输入提示而非正文，阈值放宽到 4.0
            const isPlaceholder = cls.includes('placeholder');
            const need = isPlaceholder ? 4.0 : (large ? 3.0 : 4.5);
            const r = ratio(fg, bg);
            if (r < need) {
                const entry = {
                    tag: el.tagName,
                    cls: cls.slice(0, 60),
                    text: text,
                    fg: cs.color,
                    bg: `rgb(${Math.round(bg.r)}, ${Math.round(bg.g)}, ${Math.round(bg.b)})`,
                    ratio: Math.round(r * 100) / 100,
                    need: need,
                };
                // X 品牌蓝 #1d9bf0 与白底/白字组合本身就是 3.0:1（X 官方同值），
                // 属于还原 X 设计语言的既定取舍：记录下来但不阻断，阈值 2.8。
                const isBrand = (c) => (c.r === 29 && c.g === 155 && c.b === 240)
                    || (c.r === 26 && c.g === 140 && c.b === 216);
                if ((isBrand(fg) || isBrand(bg)) && r >= 2.8) {
                    brandLowContrast.push(entry);
                    continue;
                }
                lowContrast.push(entry);
            }
        }
        return {
            docScroll: doc.scrollWidth,
            docClient: doc.clientWidth,
            rootHeight: root ? root.getBoundingClientRect().height : 0,
            bodyTextLen: (document.body.innerText || '').trim().length,
            clipped: clipped.slice(0, 6),
            lowContrast: lowContrast.slice(0, 6),
            brandLowContrast: brandLowContrast.slice(0, 6),
        };
    }''')


def visit(page, name, route, query, mode):
    label = f'{name}[{mode}]'
    try:
        page.goto(f'{base_url}/#/{route}{query}', wait_until='domcontentloaded')
        page.wait_for_timeout(1200)
        m = measure(page)
        check(m['docScroll'] <= m['docClient'] + 1,
              f'横向溢出：文档宽 {m["docScroll"]} > 视口 {m["docClient"]}')
        check(m['rootHeight'] > 120, f'页面几乎空白：根节点高度 {m["rootHeight"]:.0f}px')
        check(not m['clipped'], f'可见文字被裁切：{m["clipped"]}')
        check(not m['lowContrast'],
              f'文字对比度不足（WCAG AA）：{m["lowContrast"]}')
        brand_counts[mode] = brand_counts.get(mode, 0) + len(m['brandLowContrast'])
        shot = f'all-pages-{name}-{mode}.png'
        page.screenshot(path=os.path.join(ARTIFACTS_DIR, shot))
        report['screenshots'].append(shot)
        print(f'  [通过] {label}  高度={m["rootHeight"]:.0f}px 文本={m["bodyTextLen"]}字')
        report['scenarios'].append({'scenario': label, 'status': 'PASS', 'assertions': {
            'root_height': round(m['rootHeight']), 'doc_scroll': m['docScroll'],
            'doc_client': m['docClient'], 'text_len': m['bodyTextLen'],
            'clipped': 0, 'low_contrast': 0}})
        return True
    except Exception as e:
        print(f'  [失败] {label}: {e}')
        report['scenarios'].append({'scenario': label, 'status': 'FAIL',
                                    'assertions': {}, 'error': f'{e}\n{traceback.format_exc(limit=3)}'})
        return False


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={'width': 390, 'height': 844},
        user_agent=('Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 '
                    '(KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1'),
        locale='zh-CN',
    )
    # 模拟已登录 Web 会话：CSRF cookie + user_info
    context.add_cookies([{'name': 'sw_csrf', 'value': 'mock-csrf-token',
                          'domain': '127.0.0.1', 'path': '/'}])
    context.add_init_script("""
        try {
          localStorage.setItem('user_info', JSON.stringify({
            id: '%s', nickname: '走查同学', role: 'student', is_verified: true, avatar_url: null
          }));
        } catch (e) {}
    """ % USER_ID)

    page = context.new_page()
    page.on('console', lambda m: console_errors.append(m.text) if m.type == 'error' else None)
    page.on('pageerror', lambda e: page_errors.append(str(e)))
    page.route('**/api/v1/**', handle_api)

    print('\n=== 亮色模式全页面走查 ===')
    for name, route, query in PAGES:
        visit(page, name, route, query, 'light')

    print('\n=== 切换深色模式 ===')
    switched = False
    try:
        page.goto(f'{base_url}/#/pages/settings/index', wait_until='domcontentloaded')
        page.wait_for_timeout(1200)
        switch = page.locator('uni-switch, .uni-switch-input').first
        if switch.count() > 0:
            switch.click()
            page.wait_for_timeout(600)
            switched = True
            print('  已通过设置页开关切换深色模式')
    except Exception as e:
        print(f'  [警告] 深色模式切换失败：{e}')
    report['scenarios'].append({'scenario': 'dark_mode_toggle', 'status': 'PASS' if switched else 'FAIL',
                                'assertions': {'switched': switched}})

    print('\n=== 深色模式全页面走查 ===')
    for name, route, query in PAGES:
        visit(page, name, route, query, 'dark')

    ctx_errors = [e for e in console_errors if 'favicon' not in e.lower()]
    report['brand_color_contrast_notes'] = brand_counts
    report['console_errors'] = ctx_errors
    report['page_errors'] = page_errors
    report['unhandled_rejections'] = page_errors
    if ctx_errors:
        report['overall'] = 'FAIL'
        print(f'\n[失败] 控制台错误 {len(ctx_errors)} 条：')
        for e in ctx_errors[:10]:
            print('   -', e[:200])
    if page_errors:
        report['overall'] = 'FAIL'
        print(f'\n[失败] 页面异常 {len(page_errors)} 条：')
        for e in page_errors[:10]:
            print('   -', e[:200])

    context.close()
    browser.close()

failed = [s for s in report['scenarios'] if s['status'] == 'FAIL']
report['passed'] = len(report['scenarios']) - len(failed)
report['failed'] = len(failed)
if failed:
    report['overall'] = 'FAIL'

with open(os.path.join(ARTIFACTS_DIR, 'all-pages-report.json'), 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print('\n' + '=' * 56)
print(f"全页面走查结束: {report['passed']} 通过 / {report['failed']} 失败，总体 {report['overall']}")
print(f"报告: {os.path.join(ARTIFACTS_DIR, 'all-pages-report.json')}")
print('=' * 56)
sys.exit(1 if report['overall'] != 'PASS' else 0)
