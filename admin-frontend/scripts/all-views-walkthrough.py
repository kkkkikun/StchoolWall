#!/usr/bin/env python3
"""
SchoolWall 管理后台「全视图」Playwright 走查

覆盖 router 注册的全部业务路由 × 桌面/窄屏双视口，逐页断言：
  1. 路由可达且页面有真实渲染内容（空白页/崩溃即失败）
  2. 文档级横向溢出（表格与弹窗在窄屏塌陷）
  3. 可见文本被裁切（overflow:visible 下的文字溢出）
  4. 控制台错误与未处理 Promise 异常
  5. Element Plus 组件未挂载（顶栏/侧边栏缺失）

产物：ci-artifacts/admin-ui/all-views-report.json + all-views-*.png
任一断言失败 -> 该场景 FAIL，退出码非零。全部走 Mock API，不连真实后端。
"""

import json
import os
import sys
import time
import traceback

from playwright.sync_api import sync_playwright

from walkthrough_server import create_server, route_url  # 同目录共享模块

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIST_DIR = os.path.join(ROOT_DIR, 'admin-frontend', 'dist')
ARTIFACTS_DIR = os.path.join(ROOT_DIR, 'ci-artifacts', 'admin-ui')
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

if not os.path.isdir(DIST_DIR):
    print(f"Error: DIST_DIR not found at {DIST_DIR}. Run 'npm run build' in admin-frontend first.", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------- 静态服务（SPA 回退）
httpd, base_url = create_server(DIST_DIR)
print(f'Admin static server listening on {base_url}')

# ---------------------------------------------------------------- Mock 夹具
NOW = '2026-10-25T08:00:00Z'


def ok(data):
    return {'code': 0, 'data': data}


def list_page(rows, total=None):
    return ok({'items': rows, 'total': len(rows) if total is None else total,
               'page': 1, 'page_size': 20, 'has_more': False})


AUTHOR = {'nickname': '走查同学', 'id': 'u-1', 'avatar_url': None, 'is_verified': True}

POSTS = [{
    'id': i, 'post_type': ['general', 'second_hand', 'lost_found'][i % 3],
    'category': ['广场', '二手', '失物'][i % 3],
    'content': f'第{i}条走查用帖子：用于验证管理端列表、筛选与状态徽标渲染，内容需要足够长以便观察排版。',
    'images': [], 'images_count': 0, 'price': 99.0 if i % 3 == 1 else None,
    'status': [1, 0, -1][i % 3], 'is_pinned': i == 2, 'is_featured': i == 3,
    'author': AUTHOR, 'like_count': i, 'comment_count': i % 5, 'view_count': 100 + i,
    'created_at': NOW,
} for i in range(1, 9)]

USERS = [{
    'id': f'u-{i}', 'username': f'user{i}', 'nickname': f'用户{i}', 'avatar_url': None,
    'role': 'student', 'status': 1, 'is_verified': i % 2 == 0,
    'post_count': i, 'comment_count': i, 'like_count': i,
    'created_at': NOW, 'last_login_at': NOW,
} for i in range(1, 7)]

REPORTS = [{
    'id': i, 'reason': '不友善言论', 'description': '举报说明，用于验证举报列表渲染。',
    'status': 'pending', 'reporter': AUTHOR, 'target_post_id': i,
    'created_at': NOW, 'handled_at': None,
} for i in range(1, 5)]

COMMENTS = [{
    'id': i, 'content': f'第{i}条走查用评论：验证评论管理与软删状态展示。',
    'post_id': i, 'post_content': '被评论的帖子标题', 'user': AUTHOR,
    'status': 1, 'created_at': NOW,
} for i in range(1, 5)]

PARTIES = [{
    'id': i, 'type': 'group', 'category': '学习', 'title': f'第{i}个组局',
    'content': '组局说明，用于验证组局管理列表。', 'total': 6, 'joined_count': i,
    'status': 1, 'meet_time': NOW, 'location': '图书馆',
    'organizer': {'nickname': '走查同学', 'id': 'u-1'}, 'created_at': NOW,
} for i in range(1, 4)]

BANNERS = [{
    'id': i, 'title': f'轮播位{i}', 'image_url': None, 'link_url': None,
    'sort': i, 'status': 1, 'start_at': NOW, 'end_at': NOW, 'created_at': NOW,
} for i in range(1, 4)]

ANNOUNCEMENTS = [{
    'id': i, 'title': f'公告{i}', 'content': '公告正文内容，用于验证公告群发列表。',
    'status': 1, 'created_at': NOW, 'sent_count': i,
} for i in range(1, 4)]

LOGS = [{
    'id': i, 'admin_name': '走查管理员', 'action': 'post.status', 'target_type': 'post',
    'target_id': str(i), 'detail': '操作详情，用于验证日志列表渲染。',
    'ip': '127.0.0.1', 'created_at': NOW,
} for i in range(1, 5)]

SENSITIVE = [{'id': i, 'word': f'违禁词{i}', 'category': '其他', 'status': 1, 'created_at': NOW}
             for i in range(1, 4)]

MOD_RECORDS = [{
    'id': i, 'source': 'rule', 'decision': 'pass', 'reason': '命中本地敏感词',
    'trace_id': f'trace-{i}', 'created_at': NOW,
} for i in range(1, 4)]

VERIFICATIONS = [{
    'id': f'v-{i}', 'user_id': 'u-1', 'username': f'user{i}', 'nickname': f'用户{i}',
    'school_id': 'demo', 'status': 'pending', 'consent_version': 'v1',
    'submitted_at': NOW, 'created_at': NOW,
} for i in range(1, 4)]

APPEALS = [{
    'id': f'a-{i}', 'entity_type': 'post', 'entity_id': str(i),
    'user': {'nickname': f'用户{i}', 'id': f'u-{i}'}, 'reason': '误判申诉说明文本',
    'status': 'pending', 'created_at': NOW,
} for i in range(1, 4)]

MODERATION_JOBS = [{
    'id': f'j-{i}', 'kind': 'moderate_post', 'status': 'review', 'attempts': 1,
    'payload': {'post_id': i}, 'created_at': NOW, 'available_at': NOW,
} for i in range(1, 4)]

ADMIN_ACCOUNTS = [{
    'id': f'a-{i}', 'username': f'admin{i}', 'display_name': f'管理员{i}',
    'role': 'superadmin' if i == 1 else 'operator', 'status': 1,
    'mfa_enabled': i == 1, 'created_at': NOW, 'last_login_at': NOW,
} for i in range(1, 3)]

TAGS = [{'id': i, 'name': f'标签{i}', 'post_count': i * 3} for i in range(1, 4)]

ACTIVITIES = [{
    'id': i, 'title': f'活动{i}', 'content': '活动说明正文。', 'image_url': None,
    'location': '大学生活动中心', 'start_at': NOW, 'end_at': NOW, 'status': 1,
    'created_at': NOW,
} for i in range(1, 3)]


def handle_api(route):
    url = route.request.url
    if '/admin/auth/me' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(ok({
            'admin': {'id': 'a-1', 'username': 'boss', 'display_name': '走查管理员',
                      'role': 'superadmin', 'mfa_enabled': True},
            'password_version': 1,
        })))
    elif '/admin/stats/trends' in url:
        # 契约：{days: number, series: TrendPoint[]}（不是 {days: [...]}）
        days = [{'date': f'2026-10-{d:02d}', 'posts': d, 'comments': d * 2,
                 'likes': d * 3, 'new_users': d, 'active_users': d * 4} for d in range(1, 15)]
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps(ok({'days': 14, 'series': days})))
    elif '/admin/stats' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(ok({
            'pending_posts': 3, 'pending_reports': 2, 'posts_today': 12,
            'total_posts': 156, 'total_users': 89, 'frozen_users': 1})))
    elif '/admin/posts/feature-candidates' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(ok({'items': POSTS[:2]})))
    elif '/admin/posts' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(list_page(POSTS)))
    elif '/admin/users' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(list_page(USERS)))
    elif '/admin/reports' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(list_page(REPORTS)))
    elif '/admin/comments' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(list_page(COMMENTS)))
    elif '/admin/parties' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(list_page(PARTIES)))
    elif '/admin/banners' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(list_page(BANNERS)))
    elif '/admin/announcements' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(list_page(ANNOUNCEMENTS)))
    elif '/admin/logs' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(list_page(LOGS)))
    elif '/admin/sensitive-words' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(list_page(SENSITIVE)))
    elif '/admin/moderation-records' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(list_page(MOD_RECORDS)))
    elif '/admin/student-verifications' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(list_page(VERIFICATIONS)))
    elif '/admin/appeals' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(list_page(APPEALS)))
    elif '/admin/moderation-jobs' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(list_page(MODERATION_JOBS)))
    elif '/admin/admins' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(list_page(ADMIN_ACCOUNTS)))
    elif '/admin/tags' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(list_page(TAGS)))
    elif '/admin/activities' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(list_page(ACTIVITIES)))
    else:
        route.fulfill(status=200, content_type='application/json', body=json.dumps(ok({'items': []})))


# ---------------------------------------------------------------- 路由清单
ROUTES = [
    ('dashboard', '/dashboard'),
    ('posts', '/posts'),
    ('moderation-jobs', '/moderation-jobs'),
    ('appeals', '/appeals'),
    ('moderation-records', '/moderation-records'),
    ('sensitive-words', '/sensitive-words'),
    ('student-verifications', '/student-verifications'),
    ('users', '/users'),
    ('reports', '/reports'),
    ('comments', '/comments'),
    ('parties', '/parties'),
    ('banners', '/banners'),
    ('announcements', '/announcements'),
    ('logs', '/logs'),
    ('admins', '/admins'),
    ('tags', '/tags'),
    ('activities', '/activities'),
]

VIEWPORTS = [('desktop', 1280, 800), ('narrow', 390, 844)]

report = {
    'task': 'admin all-views browser acceptance (every router route x desktop/narrow)',
    'date_utc': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
    'base_url': base_url,
    'browser': 'chromium(headless, single instance, serial)',
    'mock_scope': 'All /api/v1/admin/** intercepted locally with synthetic fixtures; no real backend.',
    'routes_checked': len(ROUTES),
    'scenarios': [],
    'screenshots': [],
    'overall': 'PASS',
}

console_errors: list[str] = []
page_errors: list[str] = []
brand_counts: dict[str, int] = {}
charts: dict[str, int] = {}


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def measure(page):
    return page.evaluate('''() => {
        const doc = document.documentElement;
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
            const cls = (el.className && el.className.toString ? el.className.toString() : '');
            const text = el.textContent.trim().slice(0, 30);
            if (el.scrollWidth > el.clientWidth + 4 && cs.overflowX === 'visible') {
                clipped.push({
                    tag: el.tagName,
                    cls: cls.slice(0, 60),
                    text: text,
                    scrollWidth: el.scrollWidth,
                    clientWidth: el.clientWidth,
                });
            }
            if (el.closest('[disabled], .is-disabled, .el-button.is-disabled, .el-input.is-disabled')) continue;
            if (parseFloat(cs.opacity) < 0.6) continue;
            const fg = parseColor(cs.color);
            const bg = effectiveBg(el);
            if (!fg || !bg) continue;
            const size = parseFloat(cs.fontSize) || 16;
            const weight = parseInt(cs.fontWeight, 10) || 400;
            const large = size >= 24 || (size >= 18.66 && weight >= 700);
            const need = large ? 3.0 : 4.5;
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
                const isBrand = (c) => (c.r === 29 && c.g === 155 && c.b === 240)
                    || (c.r === 26 && c.g === 140 && c.b === 216);
                if ((isBrand(fg) || isBrand(bg)) && r >= 2.8) { brandLowContrast.push(entry); continue; }
                lowContrast.push(entry);
            }
        }
        return {
            docScroll: doc.scrollWidth,
            docClient: doc.clientWidth,
            bodyTextLen: (document.body.innerText || '').trim().length,
            hasLayout: !!document.querySelector('.admin-layout, aside, .el-aside, header, .el-header'),
            clipped: clipped.slice(0, 6),
            lowContrast: lowContrast.slice(0, 6),
            brandLowContrast: brandLowContrast.slice(0, 6),
        };
    }''')


def canvas_ink(page):
    """统计 ECharts 画布上真正画出来的像素数：空图（只有轴线/图例）必须被发现。"""
    return page.evaluate('''() => {
        let ink = 0;
        for (const c of document.querySelectorAll('canvas')) {
            const ctx = c.getContext('2d');
            if (!ctx || !c.width || !c.height) continue;
            const data = ctx.getImageData(0, 0, c.width, c.height).data;
            for (let i = 3; i < data.length; i += 4) {
                if (data[i] > 0) ink += 1;
            }
        }
        return ink;
    }''')


def visit(page, name, route, mode):
    label = f'{name}[{mode}]'
    try:
        page.goto(route_url(base_url, route), wait_until='domcontentloaded')
        page.wait_for_timeout(1300)
        m = measure(page)
        check(m['docScroll'] <= m['docClient'] + 1,
              f'横向溢出：文档宽 {m["docScroll"]} > 视口 {m["docClient"]}')
        check(m['bodyTextLen'] > 20, f'页面几乎空白：可见文本仅 {m["bodyTextLen"]} 字')
        check(m['hasLayout'], '管理台布局（侧边栏/顶栏）未渲染')
        check(not m['clipped'], f'可见文字被裁切：{m["clipped"]}')
        check(not m['lowContrast'], f'文字对比度不足（WCAG AA）：{m["lowContrast"]}')
        brand_counts[mode] = brand_counts.get(mode, 0) + len(m['brandLowContrast'])
        # 有 canvas 的页面（图表面板）必须真的画出像素，不能是空画布。
        # 实测：空图（仅坐标轴/图例）桌面 2297 / 窄屏 1634 像素；
        #       正常数据 桌面 22795 / 窄屏 10219 像素，阈值取 5000 留足余量。
        if page.locator('canvas').count() > 0:
            ink = canvas_ink(page)
            check(ink > 5000, f'图表画布空白：仅有 {ink} 个非透明像素（疑似接口结构不匹配导致空图）')
            charts[mode] = charts.get(mode, 0) + ink
        shot = f'all-views-{name}-{mode}.png'
        page.screenshot(path=os.path.join(ARTIFACTS_DIR, shot))
        report['screenshots'].append(shot)
        print(f'  [通过] {label}  文本={m["bodyTextLen"]}字 布局={"有" if m["hasLayout"] else "无"}')
        report['scenarios'].append({'scenario': label, 'status': 'PASS', 'assertions': {
            'text_len': m['bodyTextLen'], 'doc_scroll': m['docScroll'],
            'doc_client': m['docClient'], 'layout': m['hasLayout'], 'clipped': 0}})
        return True
    except Exception as e:
        print(f'  [失败] {label}: {e}')
        report['scenarios'].append({'scenario': label, 'status': 'FAIL', 'assertions': {},
                                    'error': f'{e}\n{traceback.format_exc(limit=3)}'})
        return False


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for mode, vw, vh in VIEWPORTS:
        context = browser.new_context(viewport={'width': vw, 'height': vh}, locale='zh-CN')
        context.add_cookies([
            {'name': 'sw_admin', 'value': 'mock-admin-token', 'domain': '127.0.0.1', 'path': '/'},
            {'name': 'sw_admin_csrf', 'value': 'mock-csrf-token', 'domain': '127.0.0.1', 'path': '/'},
        ])
        context.add_init_script("""
            try {
              localStorage.setItem('sw_admin_name', '走查管理员');
              localStorage.setItem('sw_admin_username', 'boss');
              localStorage.setItem('sw_admin_id', 'a-1');
            } catch (e) {}
        """)
        page = context.new_page()
        page.on('console', lambda m: console_errors.append(m.text) if m.type == 'error' else None)
        page.on('pageerror', lambda e: page_errors.append(str(e)))
        page.route('**/api/v1/**', handle_api)

        print(f'\n=== {mode} ({vw}x{vh}) 全视图走查 ===')
        for name, route in ROUTES:
            visit(page, name, route, mode)

        context.close()

    browser.close()

ctx_errors = [e for e in console_errors if 'favicon' not in e.lower()]
report['brand_color_contrast_notes'] = brand_counts
report['chart_canvas_ink_pixels'] = charts
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

failed = [s for s in report['scenarios'] if s['status'] == 'FAIL']
report['passed'] = len(report['scenarios']) - len(failed)
report['failed'] = len(failed)
if failed:
    report['overall'] = 'FAIL'

with open(os.path.join(ARTIFACTS_DIR, 'all-views-report.json'), 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print('\n' + '=' * 56)
print(f"全视图走查结束: {report['passed']} 通过 / {report['failed']} 失败，总体 {report['overall']}")
print(f"报告: {os.path.join(ARTIFACTS_DIR, 'all-views-report.json')}")
print('=' * 56)
sys.exit(1 if report['overall'] != 'PASS' else 0)
