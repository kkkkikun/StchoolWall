#!/usr/bin/env python3
"""
SchoolWall 管理后台 举报处理页（ReportsView.vue）真实浏览器验收
（独立脚本；静态 dist + 单 Chromium 串行；Mock API，非真实后端联调）

场景：
  R1 初始加载（默认待处理、参数契约）
  R2 全部切换与分页
  R3 列表字段展示（举报人/理由/内容/补充/双状态标签）
  R4 原帖抽屉（完整字段 + 无图/无补充/缺作者的合法边界）
  R5 抽屉图片预览
  R6 驳回举报（确认/请求体/刷新/待处理剔除）
  R7 封禁帖子
  R8 封帖并封禁作者
  R9 取消确认零写请求
  R10 业务错误（该举报已处理）与重试
  R11 网络中断与重试
  R12 处置后筛选一致性（pending 视图剔除、全部视图状态正确）
  R13 响应式 768/390（抽屉与操作按钮可用性、横向溢出）

产物：ci-artifacts/admin-ui/reports-view-report.json + reports-*.png
任一断言失败 -> 场景 FAIL，退出码非零。
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
DIST_DIR = os.path.join(ROOT_DIR, 'admin-frontend', 'dist')
ARTIFACTS_DIR = os.path.join(ROOT_DIR, 'ci-artifacts', 'admin-ui')
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

if not os.path.isdir(DIST_DIR):
    print(f"Error: DIST_DIR not found at {DIST_DIR}. Run 'npm run build' in admin-frontend first.", file=sys.stderr)
    sys.exit(1)

PNG_DATA_URI = ('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4'
                'nGP4z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg==')

# ---------------------------------------------------------------- 静态服务
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind(('127.0.0.1', 0))
port = sock.getsockname()[1]
sock.close()

class SPAHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST_DIR, **kwargs)
    def do_GET(self):
        clean = self.path.split('?')[0].split('#')[0].lstrip('/')
        full = os.path.join(DIST_DIR, clean)
        if not (clean and os.path.exists(full) and not os.path.isdir(full)):
            self.path = '/index.html'
        return super().do_GET()
    def copyfile(self, source, outputfile):
        try:
            super().copyfile(source, outputfile)
        except (ConnectionResetError, BrokenPipeError):
            pass
    def log_message(self, format, *args):
        pass

socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(('127.0.0.1', port), SPAHandler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
base_url = f'http://127.0.0.1:{port}'
print(f'Admin static server listening on {base_url}')

# ---------------------------------------------------------------- Mock 状态
requests_log = []
flags = {'handle_error': False, 'handle_abort': False}

def make_report(i, status='pending'):
    return {
        'id': 100 + i,
        'post_id': 500 + i,
        'post_content': f'被举报帖子摘要 {i}号：图书馆自习室相关讨论',
        'post_full_content': f'被举报帖子完整正文 {i}号：关于图书馆自习室预约规则的详细讨论内容。',
        'post_images': [PNG_DATA_URI, PNG_DATA_URI] if i % 3 == 1 else [],
        'post_type': 'general',
        'post_category': '校园生活' if i % 2 else None,
        'post_status': 1,
        'author': {'id': f'u{i}', 'nickname': f'作者{i}'} if i % 3 != 2 else None,  # 1/3 缺作者（合法边界）
        'reporter': {'id': f'r{i}', 'nickname': f'举报人{i}'},
        'reason': ['垃圾广告', '人身攻击', '虚假信息'][i % 3],
        'description': f'补充说明：第{i}条证据描述' if i % 2 else None,
        'status': status,
        'created_at': f'2026-10-{min(i, 28):02d}T09:00:00Z',
    }

# 25 条待处理 + 2 条已处理
REPORTS = [make_report(i) for i in range(1, 26)] + [make_report(30, 'dismissed'), make_report(31, 'resolved')]
REPORTS[25]['post_status'] = -1
REPORTS[26]['post_status'] = -1

def reports_page(query):
    items = list(REPORTS)
    st = query.get('status')
    if st:
        items = [r for r in items if r['status'] == st]
    total = len(items)
    page = int(query.get('page', 1))
    size = int(query.get('page_size', 20))
    return items[(page - 1) * size: page * size], total

def fulfill(route, data, status=200):
    route.fulfill(status=status, content_type='application/json', body=json.dumps(data))

def handle_admin_api(route):
    req = route.request
    u = urllib.parse.urlparse(req.url)
    path = u.path
    query = dict(urllib.parse.parse_qsl(u.query))
    body = None
    if req.method in ('POST', 'PUT', 'PATCH'):
        try:
            body = json.loads(req.post_data or '{}')
        except Exception:
            body = None
    if '/admin/' not in path and '/api/v1/' not in path:
        return route.continue_()

    if path.endswith('/admin/auth/me'):
        return fulfill(route, {'code': 0, 'data': {'id': 'a1', 'username': 'admin',
                       'display_name': '系统管理员', 'role': 'super_admin', 'mfa_enabled': True}})
    if '/admin/reports/' in path and req.method == 'PUT':
        if flags['handle_abort']:
            return route.abort()
        rid = int(path.rstrip('/').rsplit('/', 1)[-1])
        requests_log.append({'method': 'PUT', 'path': path, 'query': query, 'body': body})
        if flags['handle_error']:
            return fulfill(route, {'detail': '该举报已处理'}, status=400)
        action = (body or {}).get('action')
        for r in REPORTS:
            if r['id'] == rid:
                r['status'] = 'dismissed' if action == 'dismiss' else 'resolved'
                if action in ('ban_post', 'ban_user'):
                    r['post_status'] = -1
        return fulfill(route, {'code': 0, 'message': '处理成功', 'data': {'post_id': 500 + rid - 100}})
    if path.endswith('/admin/reports'):
        requests_log.append({'method': 'GET', 'path': path, 'query': query, 'body': None})
        items, total = reports_page(query)
        return fulfill(route, {'code': 0, 'data': {'items': items, 'total': total,
                       'page': int(query.get('page', 1)), 'page_size': int(query.get('page_size', 20)),
                       'next_cursor': None, 'has_more': False}})
    return fulfill(route, {'code': 0, 'message': 'ok', 'data': {'items': [], 'total': 0}})

# ---------------------------------------------------------------- 工具
class ScenarioFailure(Exception):
    pass

def check(cond, msg):
    if not cond:
        raise ScenarioFailure(msg)

report = {
    'task': 'admin ReportsView.vue browser acceptance',
    'date_utc': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
    'base_url': base_url,
    'browser': 'chromium(headless, single instance, serial)',
    'mock_scope': 'All /api/v1/admin/** intercepted locally with contract fixtures; no real backend, no real credentials.',
    'scenarios': [],
    'screenshots': [],
    'overall': 'PASS',
}

def record(name, viewport, status, assertions=None, error=None, screenshots=None):
    report['scenarios'].append({'scenario': name, 'viewport': viewport, 'status': status,
                                'assertions': assertions or {}, 'error': error,
                                'screenshots': screenshots or []})
    if screenshots:
        report['screenshots'].extend(screenshots)
    if status != 'PASS':
        report['overall'] = 'FAIL'

def shot(page, filename):
    page.screenshot(path=f'{ARTIFACTS_DIR}/{filename}')
    return filename

def last_requests(method, path_part, n=1):
    out = [r for r in requests_log if r['method'] == method and path_part in r['path']]
    return out[-n:] if n else out

def count_requests(method, path_part):
    return sum(1 for r in requests_log if r['method'] == method and path_part in r['path'])

def msg_text(page):
    m = page.locator('.el-message')
    return m.last.inner_text().strip() if m.count() else ''

def msg_has_error(page):
    return page.locator('.el-message--error').count() > 0

def confirm_box(page, confirm=True):
    page.wait_for_selector('.el-message-box', timeout=5000)
    btn = page.locator('.el-message-box__btns button').last if confirm else page.locator('.el-message-box__btns button').first
    btn.click()
    page.wait_for_timeout(400)

def new_admin_context(browser, width, height):
    ctx = browser.new_context(viewport={'width': width, 'height': height})
    ctx.add_cookies([
        {'name': 'sw_admin', 'value': 'mock-admin-token', 'domain': '127.0.0.1', 'path': '/'},
        {'name': 'sw_admin_csrf', 'value': 'mock-csrf-token', 'domain': '127.0.0.1', 'path': '/'},
    ])
    page = ctx.new_page()
    page.route('**/api/v1/**', handle_admin_api)
    return ctx, page

def doc_overflow(page):
    return page.evaluate('''() => {
        const d = document.documentElement, b = document.body;
        return { sw: Math.max(d.scrollWidth, b.scrollWidth), cw: d.clientWidth };
    }''')

def pager_total(page):
    return page.locator('.el-pagination__total').inner_text().strip()

exit_code = 0
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx, page = new_admin_context(browser, 1280, 800)
        VP = '1280x800'

        # ================= R1 初始加载 =================
        print('\n--- R1 初始加载（默认待处理） ---')
        try:
            page.goto(f'{base_url}/reports')
            page.wait_for_selector('.el-table__row', timeout=8000)
            page.wait_for_timeout(600)
            check(page.locator('.el-table__row').count() == 20, '待处理首页应渲染 20 行')
            check('25' in pager_total(page), f'待处理总数应为 25，实际: {pager_total(page)}')
            q = last_requests('GET', '/admin/reports')[0]['query']
            check(q.get('status') == 'pending' and q.get('page') == '1' and q.get('page_size') == '20',
                  f'初始参数应为 status=pending&page=1&page_size=20，实际: {q}')
            check(page.locator('.el-loading-mask').count() == 0, '加载态应结束')
            s = shot(page, 'reports-r1-loaded.png')
            print('   [通过] 20 行 / 待处理 25 条 / 参数契约正确')
            record('R1_initial_load', VP, 'PASS',
                   assertions={'rows': 20, 'total_pending': 25, 'params': q}, screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('R1_initial_load', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= R2 全部切换与分页 =================
        print('\n--- R2 全部切换与分页 ---')
        try:
            page.locator('.el-radio-button:has-text("全部")').click()
            page.wait_for_timeout(800)
            q = last_requests('GET', '/admin/reports')[0]['query']
            check('status' not in q, f'「全部」不应带 status 参数，实际: {q}')
            check('27' in pager_total(page), f'全部总数应为 27，实际: {pager_total(page)}')

            page.locator('.el-pager li.number', has_text='2').first.click()
            page.wait_for_timeout(800)
            q = last_requests('GET', '/admin/reports')[0]['query']
            check(q.get('page') == '2', f'翻页应带 page=2，实际: {q}')
            check(page.locator('.el-table__row').count() == 7,
                  f'第 2 页应为 7 行（27-20），实际 {page.locator(".el-table__row").count()}')
            print('   [通过] 全部无 status 参数、总数 27、第 2 页 7 行')
            record('R2_all_filter_pagination', VP, 'PASS',
                   assertions={'all_no_status': True, 'total_all': 27, 'page2_rows': 7})
        except Exception as e:
            print(f'   [失败] {e}')
            record('R2_all_filter_pagination', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # 回到待处理第 1 页
        page.locator('.el-radio-button:has-text("待处理")').click()
        page.wait_for_timeout(800)

        # ================= R3 列表字段展示 =================
        print('\n--- R3 列表字段展示 ---')
        try:
            row1 = page.locator('.el-table__row').first
            text = row1.inner_text()
            check('举报人1' in text, '应显示举报人昵称')
            check('人身攻击' in row1.locator('.el-tag').first.inner_text(), '理由标签应为人身攻击（夹具 i=1）')
            check('被举报帖子摘要 1号' in text, '应显示帖子摘要')
            check('举报补充：补充说明：第1条证据描述' in text, '应显示补充说明')
            check('展示中' in text, '帖子状态应为展示中')
            check('待处理' in text, '处理状态应为待处理')
            check(row1.locator('.post-mini-thumb').count() == 1, '有图举报应显示缩略图')
            row2 = page.locator('.el-table__row').nth(1)
            check(row2.locator('.post-mini-thumb').count() == 0, '无图举报不应显示缩略图')
            s = shot(page, 'reports-r3-fields.png')
            print('   [通过] 举报人/理由/摘要/补充/双状态/缩略图展示正确')
            record('R3_list_fields', VP, 'PASS',
                   assertions={'fields_ok': True, 'thumb_present': True, 'no_thumb_row2': True},
                   screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('R3_list_fields', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= R4 原帖抽屉 + 边界 =================
        print('\n--- R4 原帖抽屉与合法边界数据 ---')
        try:
            # 完整数据（行 1：有图、有补充、有作者、有分类）
            page.locator('.el-table__row').first.locator('button:has-text("查看原帖")').click()
            page.wait_for_selector('.el-drawer:visible', timeout=5000)
            page.wait_for_timeout(500)
            drawer = page.locator('.el-drawer:visible')
            check('原帖审查 - 帖子 #501' in drawer.inner_text(), '抽屉标题应含帖子 ID')
            check('被举报理由：人身攻击' in drawer.inner_text(), '抽屉应显示理由')
            check('说明：补充说明：第1条证据描述' in drawer.inner_text(), '抽屉应显示补充说明')
            check('作者1' in drawer.inner_text() and '(ID: u1)' in drawer.inner_text(), '应显示作者与 ID')
            check('举报人1' in drawer.inner_text(), '应显示举报人')
            check('校园生活' in drawer.inner_text(), '应显示分类标签')
            check('完整正文 1号' in drawer.inner_text(), '应显示完整正文')
            check(drawer.locator('.drawer-img').count() == 2, '应显示 2 张配图')
            s = shot(page, 'reports-r4-drawer.png')
            page.locator('.el-drawer:visible .el-drawer__close-btn').click()
            page.wait_for_timeout(500)

            # 边界数据（行 2：缺作者、无图、无补充）
            page.locator('.el-table__row').nth(1).locator('button:has-text("查看原帖")').click()
            page.wait_for_selector('.el-drawer:visible', timeout=5000)
            page.wait_for_timeout(500)
            drawer = page.locator('.el-drawer:visible')
            check('未知用户' in drawer.inner_text() and '(ID: —)' in drawer.inner_text(),
                  f'缺作者应降级显示未知用户，实际: {drawer.inner_text()[:200]}')
            check('举报人未提供额外补充说明' in drawer.inner_text(), '无补充应显示默认文案')
            check(drawer.locator('.drawer-img').count() == 0, '无图不应渲染图片网格')
            check('完整正文 2号' in drawer.inner_text(), '边界数据正文应正常显示')
            page.locator('.el-drawer:visible .el-drawer__close-btn').click()
            page.wait_for_timeout(500)
            print('   [通过] 完整字段 + 缺作者/无图/无补充边界均不崩溃')
            record('R4_drawer_fields_boundary', VP, 'PASS',
                   assertions={'full_fields': True, 'missing_author_fallback': True,
                               'no_image_no_desc_ok': True}, screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('R4_drawer_fields_boundary', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= R5 抽屉图片预览 =================
        print('\n--- R5 抽屉图片预览 ---')
        try:
            page.locator('.el-table__row').first.locator('button:has-text("查看原帖")').click()
            page.wait_for_selector('.el-drawer:visible', timeout=5000)
            page.wait_for_timeout(500)
            page.locator('.el-drawer:visible .drawer-img').first.click()
            page.wait_for_timeout(800)
            check(page.locator('.el-image-viewer__wrapper').count() >= 1, '点击图片应打开预览层')
            page.locator('.el-image-viewer__close').click()
            page.wait_for_timeout(500)
            check(page.locator('.el-image-viewer__wrapper').count() == 0, '预览层应可关闭')
            page.locator('.el-drawer:visible .el-drawer__close-btn').click()
            page.wait_for_timeout(400)
            print('   [通过] 图片预览打开/关闭正常')
            record('R5_image_preview', VP, 'PASS', assertions={'preview_open_close': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('R5_image_preview', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= R6 驳回举报 =================
        print('\n--- R6 驳回举报 ---')
        try:
            puts_before = count_requests('PUT', '/admin/reports/101')
            page.locator('.el-table__row').first.locator('button:has-text("驳回")').click()
            page.wait_for_selector('.el-message-box', timeout=5000)
            check('驳回该举报（判定帖子合规）' in page.locator('.el-message-box').inner_text(),
                  '确认文案应为驳回语义')
            confirm_box(page, confirm=True)
            page.wait_for_timeout(1000)
            check(count_requests('PUT', '/admin/reports/101') - puts_before == 1, '应发 1 次 PUT')
            body = last_requests('PUT', '/admin/reports/101')[0]['body']
            check(body == {'action': 'dismiss'}, f'驳回请求体应为 {{"action":"dismiss"}}，实际: {body}')
            check('处理成功' in msg_text(page), f'应有成功提示，实际: 「{msg_text(page)}」')
            page.wait_for_timeout(600)
            check('24' in pager_total(page), f'待处理总数应降为 24，实际: {pager_total(page)}')
            first_row_text = page.locator('.el-table__row').first.inner_text()
            check('举报人1' not in first_row_text, '已驳回记录应从待处理视图剔除')
            print('   [通过] 确认文案/请求体/成功反馈/待处理剔除')
            record('R6_dismiss', VP, 'PASS',
                   assertions={'body': body, 'total_after': 24, 'row_removed': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('R6_dismiss', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= R7 封禁帖子 =================
        print('\n--- R7 封禁帖子 ---')
        try:
            rid7 = page.locator('.el-table__row').first.locator('td').nth(0).inner_text().strip()
            puts_before = count_requests('PUT', f'/admin/reports/{rid7}')
            page.locator('.el-table__row').first.locator('button:has-text("封帖")').click()
            page.wait_for_selector('.el-message-box', timeout=5000)
            check('封禁该帖子' in page.locator('.el-message-box').inner_text(), '确认文案应为封帖语义')
            confirm_box(page, confirm=True)
            page.wait_for_timeout(1000)
            check(count_requests('PUT', f'/admin/reports/{rid7}') - puts_before == 1, '应发 1 次 PUT')
            body = last_requests('PUT', f'/admin/reports/{rid7}')[0]['body']
            check(body == {'action': 'ban_post'}, f'封帖请求体应为 {{"action":"ban_post"}}，实际: {body}')
            check('处理成功' in msg_text(page), '应有成功提示')
            print('   [通过] 封帖请求体 ban_post 正确')
            record('R7_ban_post', VP, 'PASS', assertions={'body': body})
        except Exception as e:
            print(f'   [失败] {e}')
            record('R7_ban_post', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= R8 封帖并封禁作者（抽屉内处置 + 抽屉关闭） =================
        print('\n--- R8 封帖并封禁作者（抽屉内） ---')
        try:
            rid8 = page.locator('.el-table__row').first.locator('td').nth(0).inner_text().strip()
            puts_before = count_requests('PUT', f'/admin/reports/{rid8}')
            page.locator('.el-table__row').first.locator('button:has-text("查看原帖")').click()
            page.wait_for_selector('.el-drawer:visible', timeout=5000)
            page.wait_for_timeout(500)
            page.locator('.el-drawer:visible button:has-text("封帖并封禁作者")').click()
            page.wait_for_selector('.el-message-box', timeout=5000)
            check('封禁帖子并冻结作者' in page.locator('.el-message-box').inner_text(), '确认文案应为封号语义')
            confirm_box(page, confirm=True)
            page.wait_for_timeout(1000)
            check(count_requests('PUT', f'/admin/reports/{rid8}') - puts_before == 1, '应发 1 次 PUT')
            body = last_requests('PUT', f'/admin/reports/{rid8}')[0]['body']
            check(body == {'action': 'ban_user'}, f'封号请求体应为 {{"action":"ban_user"}}，实际: {body}')
            check('处理成功' in msg_text(page), '应有成功提示')
            page.wait_for_timeout(500)
            check(page.locator('.el-drawer:visible').count() == 0, '处置成功后抽屉应关闭')
            s = shot(page, 'reports-r8-ban-user.png')
            print('   [通过] 抽屉内封号处置、确认文案、抽屉自动关闭')
            record('R8_ban_user_drawer', VP, 'PASS',
                   assertions={'body': body, 'drawer_closed': True}, screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('R8_ban_user_drawer', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= R9 取消确认 =================
        print('\n--- R9 取消确认零写请求 ---')
        try:
            puts_before = count_requests('PUT', '/admin/reports/')
            page.wait_for_timeout(3500)  # 等待上一轮 ElMessage 自动消散，防止陈旧提示干扰
            page.locator('.el-table__row').first.locator('button:has-text("封帖")').click()
            confirm_box(page, confirm=False)
            page.wait_for_timeout(600)
            check(count_requests('PUT', '/admin/reports/') == puts_before, '取消确认不得发出写请求')
            check('处理成功' not in msg_text(page), '取消不得误报成功')
            check(not msg_has_error(page), '取消不得产生错误提示（无未处理 rejection 表象）')
            print('   [通过] 取消零请求、无误导提示、无错误提示')
            record('R9_cancel_confirm', VP, 'PASS',
                   assertions={'no_write': True, 'no_success': True, 'no_error': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('R9_cancel_confirm', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= R10 业务错误与重试 =================
        print('\n--- R10 业务错误（该举报已处理）与重试 ---')
        try:
            flags['handle_error'] = True
            page.locator('.el-table__row').first.locator('button:has-text("驳回")').click()
            confirm_box(page, confirm=True)
            page.wait_for_timeout(800)
            check('该举报已处理' in msg_text(page),
                  f'应展示后端业务错误，实际: 「{msg_text(page)}」')
            check('处理成功' not in msg_text(page), '业务错误不得误报成功')
            flags['handle_error'] = False
            page.locator('.el-table__row').first.locator('button:has-text("驳回")').click()
            confirm_box(page, confirm=True)
            page.wait_for_timeout(1000)
            check('处理成功' in msg_text(page), '恢复后重试应成功')
            print('   [通过] 业务错误正确展示、不误报、重试成功')
            record('R10_biz_error_retry', VP, 'PASS',
                   assertions={'error_toast': '该举报已处理', 'no_false_success': True,
                               'retry_success': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('R10_biz_error_retry', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            flags['handle_error'] = False

        # ================= R11 网络中断与重试 =================
        print('\n--- R11 网络中断与重试 ---')
        try:
            flags['handle_abort'] = True
            puts_before = count_requests('PUT', '/admin/reports/')
            page.locator('.el-table__row').first.locator('button:has-text("封帖")').click()
            confirm_box(page, confirm=True)
            page.wait_for_timeout(800)
            check(count_requests('PUT', '/admin/reports/') == puts_before,
                  'abort 场景请求未到达后端（拦截层中断）')
            check(msg_has_error(page), '网络中断应有错误提示')
            check('处理成功' not in msg_text(page), '网络中断不得误报成功')
            s = shot(page, 'reports-r11-network.png')
            flags['handle_abort'] = False
            page.locator('.el-table__row').first.locator('button:has-text("封帖")').click()
            confirm_box(page, confirm=True)
            page.wait_for_timeout(1000)
            check('处理成功' in msg_text(page), '网络恢复后重试应成功')
            print(f'   [通过] 网络中断错误提示（「{msg_text(page)}」），重试成功')
            record('R11_network_retry', VP, 'PASS',
                   assertions={'error_shown': True, 'no_false_success': True, 'retry_success': True},
                   screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('R11_network_retry', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            flags['handle_abort'] = False

        # ================= R12 处置后筛选一致性 =================
        print('\n--- R12 处置后筛选一致性 ---')
        try:
            total_pending_now = pager_total(page)
            page.locator('.el-radio-button:has-text("全部")').click()
            page.wait_for_timeout(800)
            all_text = page.locator('.el-table').inner_text()
            check('已驳回' in all_text or '已处理' in all_text, '全部视图应显示已处理记录的状态标签')
            page.locator('.el-radio-button:has-text("待处理")').click()
            page.wait_for_timeout(800)
            pending_text = page.locator('.el-table').inner_text()
            check('已驳回' not in pending_text, '待处理视图不得残留已驳回记录')
            handled_rows_done = page.locator('.el-table__row:has-text("—")').count()
            s = shot(page, 'reports-r12-filter-consistency.png')
            print('   [通过] 已处理记录不留在待处理视图，全部视图状态正确')
            record('R12_filter_consistency', VP, 'PASS',
                   assertions={'pending_excludes_handled': True, 'all_shows_status': True},
                   screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('R12_filter_consistency', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        ctx.close()

        # ================= R13 响应式 =================
        for label, w, h in [('tablet-768', 768, 1024), ('narrow-390', 390, 844)]:
            print(f'\n--- R13 响应式 {label} ---')
            try:
                ctx2, page2 = new_admin_context(browser, w, h)
                page2.goto(f'{base_url}/reports')
                page2.wait_for_selector('.el-table__row', timeout=8000)
                page2.wait_for_timeout(600)
                m = doc_overflow(page2)
                check(m['sw'] <= m['cw'] + 2, f'{label} 页面横向溢出: {m}')
                page2.locator('.el-table__row').first.locator('button:has-text("查看原帖")').click()
                page2.wait_for_selector('.el-drawer:visible', timeout=5000)
                page2.wait_for_timeout(600)
                dr = page2.locator('.el-drawer:visible').first.bounding_box()
                check(dr['x'] >= 0 and dr['x'] + dr['width'] <= w + 1,
                      f'{label} 抽屉超出视口: {dr} (视口 {w})')
                # 三个处置按钮在窄屏完整可操作
                for btn_text in ['驳回举报（不违规）', '违规封禁帖子', '封帖并封禁作者']:
                    btn = page2.locator(f'.el-drawer:visible button:has-text("{btn_text}")')
                    check(btn.count() == 1 and btn.is_visible(), f'{label} 缺少处置按钮「{btn_text}」')
                    box = btn.bounding_box()
                    check(box['x'] >= 0 and box['x'] + box['width'] <= w + 1,
                          f'{label} 按钮「{btn_text}」超出视口: {box}')
                m2 = doc_overflow(page2)
                check(m2['sw'] <= m2['cw'] + 2, f'{label} 抽屉打开后页面横向溢出: {m2}')
                s = shot(page2, f'reports-r13-{label}.png')
                print(f'   [通过] {label} 无溢出，抽屉与三个处置按钮完整可用')
                record(f'R13_responsive_{label}', f'{w}x{h}', 'PASS',
                       assertions={'doc': m2, 'drawer': dr, 'action_buttons_fit': True},
                       screenshots=[s])
                ctx2.close()
            except Exception as e:
                print(f'   [失败] {e}')
                record(f'R13_responsive_{label}', f'{w}x{h}', 'FAIL',
                       error=f'{e}\n{traceback.format_exc(limit=3)}')
                try:
                    shot(page2, f'reports-r13-{label}-fail.png')
                except Exception:
                    pass
                try:
                    ctx2.close()
                except Exception:
                    pass

        browser.close()
except Exception as e:
    print(f'\n[致命错误] {e}', file=sys.stderr)
    report['overall'] = 'FAIL'
    report['fatal'] = f'{e}\n{traceback.format_exc(limit=3)}'
finally:
    httpd.shutdown()

report_path = f'{ARTIFACTS_DIR}/reports-view-report.json'
with open(report_path, 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

passed = sum(1 for s in report['scenarios'] if s['status'] == 'PASS')
print(f'\n========================================================')
print(f'举报处理页验收结束: {passed}/{len(report["scenarios"])} 场景通过，总体 {report["overall"]}')
print(f'报告: {report_path}')
print(f'========================================================')

if report['overall'] != 'PASS':
    sys.exit(1)
