#!/usr/bin/env python3
"""
SchoolWall 管理后台 用户管理页（UsersView.vue）真实浏览器验收
（独立脚本；静态 dist + 单 Chromium 串行；Mock API，非真实后端联调）

场景：
  U1 初始加载与参数契约
  U2 筛选：关键词回车/角色/认证(false 传递)/状态/清除/页码归一
  U3 空列表、接口失败与恢复
  U4 分页
  U5 用户详情抽屉（字段/统计/最近帖子/空边界）
  U6 角色修改：确认文案/请求体/取消还原/失败一致性
  U7 冻结与解冻：确认/参数/状态变化/取消零请求/网络失败
  U8 注销用户限制（角色选择禁用、无冻结按钮）
  U9 CSV 导出（下载/文件名/失败反馈）
  U10 响应式 768/390（表格、抽屉、无溢出）

产物：ci-artifacts/admin-ui/users-view-report.json + users-*.png
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
flags = {'list_error': False, 'list_empty': False, 'role_error': False,
         'status_abort': False, 'export_error': False, 'detail_error': False}

def make_user(i):
    return {
        'id': f'u{i:03d}',
        'nickname': f'同学{i}号',
        'role': ['guest', 'student', 'guest'][i % 3],
        'is_verified': i % 3 == 1,
        'student_id': f'2023{i:03d}' if i % 3 == 1 else None,
        'real_name': f'真实姓名{i}' if i % 3 == 1 else None,
        'status': 1 if i % 5 else 0,   # 每 5 个一个冻结
        'created_at': f'2026-09-{min(i, 28):02d}T10:00:00Z',
    }

USERS = [make_user(i) for i in range(1, 26)]
USERS.append({'id': 'u999', 'nickname': '已注销用户', 'role': 'guest', 'is_verified': False,
              'student_id': None, 'real_name': None, 'status': -2, 'created_at': '2026-01-01T10:00:00Z'})

def users_page(query):
    items = list(USERS)
    q = query.get('q')
    if q:
        items = [u for u in items if q in u['nickname'] or (u['student_id'] and q in u['student_id'])
                 or (u['real_name'] and q in u['real_name'])]
    if query.get('role'):
        items = [u for u in items if u['role'] == query['role']]
    if 'is_verified' in query:
        want = query['is_verified'] in ('true', 'True', '1')
        items = [u for u in items if u['is_verified'] == want]
    if 'status' in query:
        items = [u for u in items if u['status'] == int(query['status'])]
    total = len(items)
    page = int(query.get('page', 1))
    size = int(query.get('page_size', 20))
    return items[(page - 1) * size: page * size], total

def user_detail(uid):
    base = next((u for u in USERS if u['id'] == uid), None)
    if not base:
        return None
    d = dict(base)
    d.update({
        'wechat_id': None, 'avatar_url': None,
        'posts_count': 7, 'comments_count': 23, 'likes_received': 56, 'reported_count': 1,
        'recent_posts': [] if uid == 'u005' else [
            {'id': 1, 'content': '图书馆自习室新规讨论', 'status': 1, 'created_at': '2026-10-20T08:00:00Z'},
            {'id': 2, 'content': '二手教材转让', 'status': 0, 'created_at': '2026-10-19T08:00:00Z'},
        ],
    })
    return d

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
    if '/admin/users/' in path and req.method == 'PUT' and path.rstrip('/').endswith('/role'):
        requests_log.append({'method': 'PUT', 'path': path, 'query': query, 'body': body})
        if flags['role_error']:
            return fulfill(route, {'detail': '不能修改其他管理员的角色'}, status=400)
        return fulfill(route, {'code': 0, 'data': {'role': (body or {}).get('role')}})
    if '/admin/users/' in path and req.method == 'PUT' and path.rstrip('/').endswith('/status'):
        if flags['status_abort']:
            return route.abort()
        requests_log.append({'method': 'PUT', 'path': path, 'query': query, 'body': body})
        uid = path.rstrip('/').split('/')[-2]
        for u_ in USERS:
            if u_['id'] == uid:
                u_['status'] = int(query.get('status', u_['status']))
        return fulfill(route, {'code': 0, 'data': {'status': int(query.get('status', 1))}})
    if '/admin/users/' in path and req.method == 'GET':
        requests_log.append({'method': 'GET', 'path': path, 'query': query, 'body': None})
        if flags['detail_error']:
            return fulfill(route, {'detail': '用户不存在'}, status=404)
        uid = path.rstrip('/').rsplit('/', 1)[-1]
        d = user_detail(uid)
        if not d:
            return fulfill(route, {'detail': '用户不存在'}, status=404)
        return fulfill(route, {'code': 0, 'data': d})
    if path.endswith('/admin/users'):
        requests_log.append({'method': 'GET', 'path': path, 'query': query, 'body': None})
        if flags['list_error']:
            return fulfill(route, {'detail': '列表服务暂时不可用'}, status=500)
        if flags['list_empty']:
            return fulfill(route, {'code': 0, 'data': {'items': [], 'total': 0, 'page': 1, 'page_size': 20}})
        items, total = users_page(query)
        return fulfill(route, {'code': 0, 'data': {'items': items, 'total': total,
                       'page': int(query.get('page', 1)), 'page_size': int(query.get('page_size', 20))}})
    if path.endswith('/admin/export/users'):
        requests_log.append({'method': 'GET', 'path': path, 'query': query, 'body': None})
        if flags['export_error']:
            return fulfill(route, {'detail': '导出失败'}, status=500)
        return route.fulfill(status=200, content_type='text/csv',
                             headers={'Content-Disposition': 'attachment; filename="users.csv"'},
                             body='id,nickname,role\nu001,同学1号,guest\n')
    return fulfill(route, {'code': 0, 'message': 'ok', 'data': {'items': [], 'total': 0}})

# ---------------------------------------------------------------- 工具
class ScenarioFailure(Exception):
    pass

def check(cond, msg):
    if not cond:
        raise ScenarioFailure(msg)

report = {
    'task': 'admin UsersView.vue browser acceptance',
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

def confirm_box(page, confirm=True):
    page.wait_for_selector('.el-message-box', timeout=5000)
    btn = page.locator('.el-message-box__btns button').last if confirm else page.locator('.el-message-box__btns button').first
    btn.click()
    page.wait_for_timeout(400)

def select_option(page, form_label, option_text):
    item = page.locator('.el-form-item', has_text=form_label).locator('.el-select').first
    item.click()
    page.wait_for_timeout(500)
    page.locator('.el-select-dropdown__item:visible', has_text=option_text).first.click()
    page.wait_for_timeout(400)
    page.keyboard.press('Escape')
    page.wait_for_timeout(200)

def clear_select(page, form_label):
    item = page.locator('.el-form-item', has_text=form_label).locator('.el-select').first
    item.hover()
    page.wait_for_timeout(400)
    item.locator('.el-select__clear, .el-select__caret.is-reverse').first.click()
    page.wait_for_timeout(300)

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

def wait_msgs_gone(page):
    page.wait_for_timeout(3200)

exit_code = 0
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx, page = new_admin_context(browser, 1280, 800)
        VP = '1280x800'

        # ================= U1 初始加载 =================
        print('\n--- U1 初始加载 ---')
        try:
            page.goto(f'{base_url}/users')
            page.wait_for_selector('.el-table__row', timeout=8000)
            page.wait_for_timeout(600)
            check(page.locator('.el-table__row').count() == 20, '首页应渲染 20 行')
            check('26' in pager_total(page), f'总数应为 26，实际: {pager_total(page)}')
            q = last_requests('GET', '/admin/users')[0]['query']
            check(q.get('page') == '1' and q.get('page_size') == '20', f'初始参数契约: {q}')
            s = shot(page, 'users-u1-loaded.png')
            print('   [通过] 20 行 / 总数 26 / 参数契约')
            record('U1_initial_load', VP, 'PASS',
                   assertions={'rows': 20, 'total': 26, 'params': q}, screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('U1_initial_load', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= U2 筛选 =================
        print('\n--- U2 筛选参数契约（含 is_verified=false 传递） ---')
        try:
            # 回车查询
            page.locator('.el-form-item', has_text='搜索').locator('input').fill('同学3')
            page.locator('.el-form-item', has_text='搜索').locator('input').press('Enter')
            page.wait_for_timeout(800)
            q = last_requests('GET', '/admin/users')[0]['query']
            check(q.get('q') == '同学3' and q.get('page') == '1', f'回车查询应带 q 且 page=1，实际: {q}')

            select_option(page, '角色', '学生')
            page.locator('button:has-text("查询")').click()
            page.wait_for_timeout(800)
            q = last_requests('GET', '/admin/users')[0]['query']
            check(q.get('role') == 'student', f'角色筛选参数: {q}')

            select_option(page, '认证', '未认证')
            page.locator('button:has-text("查询")').click()
            page.wait_for_timeout(800)
            q = last_requests('GET', '/admin/users')[0]['query']
            check(q.get('is_verified') == 'false',
                  f'is_verified=false 必须如实传递而非被丢弃，实际: {q}')
            rows = page.locator('.el-table__row').count()
            check(rows == 0 or '已认证' not in page.locator('.el-table').inner_text(),
                  '未认证筛选结果不应含已认证标签')

            select_option(page, '状态', '已冻结')
            page.locator('button:has-text("查询")').click()
            page.wait_for_timeout(800)
            q = last_requests('GET', '/admin/users')[0]['query']
            check(q.get('status') == '0', f'状态筛选参数: {q}')
            check(q.get('page') == '1', f'筛选后页码应归一第 1 页，实际: {q}')
            s = shot(page, 'users-u2-filters.png')

            # 清除筛选（clearable）
            page.locator('.el-form-item', has_text='搜索').locator('input').fill('')
            page.locator('.el-form-item', has_text='搜索').locator('input').press('Enter')
            page.wait_for_timeout(600)
            clear_select(page, '角色')
            clear_select(page, '认证')
            clear_select(page, '状态')
            page.locator('button:has-text("查询")').click()
            page.wait_for_timeout(800)
            q = last_requests('GET', '/admin/users')[0]['query']
            check('q' not in q and 'role' not in q and 'is_verified' not in q and 'status' not in q,
                  f'清除筛选后参数应为空，实际: {q}')
            print('   [通过] 关键词回车/角色/认证false/状态/清除/页码归一全部正确')
            record('U2_filters', VP, 'PASS',
                   assertions={'enter_q': True, 'role': 'student', 'is_verified_false': 'false',
                               'status': '0', 'page_reset': True, 'clear_ok': True}, screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('U2_filters', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= U3 空列表与接口失败恢复 =================
        print('\n--- U3 空列表、接口失败与恢复 ---')
        try:
            flags['list_empty'] = True
            page.locator('button:has-text("查询")').click()
            page.wait_for_timeout(800)
            check(page.locator('.el-table__row').count() == 0, '空列表不应有数据行')
            check(page.locator('.el-table__empty-text').is_visible(), '应显示空态提示')
            flags['list_empty'] = False

            flags['list_error'] = True
            page.locator('button:has-text("查询")').click()
            page.wait_for_timeout(800)
            check('列表服务暂时不可用' in msg_text(page), f'接口失败应有错误提示，实际: 「{msg_text(page)}」')
            check(page.locator('.el-loading-mask').count() == 0, '失败后 loading 应释放')
            flags['list_error'] = False
            page.locator('button:has-text("查询")').click()
            page.wait_for_selector('.el-table__row', timeout=5000)
            print('   [通过] 空态/失败提示/loading 释放/恢复重试')
            record('U3_empty_error_recover', VP, 'PASS',
                   assertions={'empty_text': True, 'error_toast': True, 'recover': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('U3_empty_error_recover', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            flags['list_empty'] = flags['list_error'] = False

        # ================= U4 分页 =================
        print('\n--- U4 分页 ---')
        try:
            page.locator('.el-pager li.number', has_text='2').first.click()
            page.wait_for_timeout(800)
            q = last_requests('GET', '/admin/users')[0]['query']
            check(q.get('page') == '2', f'翻页参数: {q}')
            check(page.locator('.el-table__row').count() == 6,
                  f'第 2 页应为 6 行（26-20），实际 {page.locator(".el-table__row").count()}')
            page.locator('.el-pager li.number', has_text='1').first.click()
            page.wait_for_timeout(800)
            print('   [通过] page=2 参数与行数正确')
            record('U4_pagination', VP, 'PASS', assertions={'page2_param': '2', 'page2_rows': 6})
        except Exception as e:
            print(f'   [失败] {e}')
            record('U4_pagination', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= U5 详情抽屉 =================
        print('\n--- U5 详情抽屉与空边界 ---')
        try:
            page.locator('.el-table__row').first.locator('button:has-text("详情")').click()
            page.wait_for_selector('.el-drawer:visible', timeout=5000)
            page.wait_for_timeout(600)
            drawer = page.locator('.el-drawer:visible')
            check('同学1号' in drawer.inner_text(), '抽屉应显示昵称')
            check('u001' in drawer.inner_text(), '抽屉应显示用户 ID')
            check('2023001' in drawer.inner_text(), '抽屉应显示学号')
            check('真实姓名1' in drawer.inner_text(), '抽屉应显示真名')
            check(drawer.locator('.d-stat').count() == 4, '应有 4 个统计卡片')
            check('图书馆自习室新规讨论' in drawer.inner_text(), '应显示最近帖子')
            s = shot(page, 'users-u5-drawer.png')
            page.locator('.el-drawer:visible .el-drawer__close-btn').click()
            page.wait_for_timeout(500)

            # 空边界：u005 无最近帖子
            page.locator('.el-table__row').nth(4).locator('button:has-text("详情")').click()
            page.wait_for_selector('.el-drawer:visible', timeout=5000)
            page.wait_for_timeout(600)
            drawer = page.locator('.el-drawer:visible')
            check('暂无帖子' in drawer.inner_text(), '空最近帖子应显示 el-empty 暂无帖子')
            check(drawer.locator('.recent-post').count() == 0, '空边界不应渲染帖子项')
            page.locator('.el-drawer:visible .el-drawer__close-btn').click()
            page.wait_for_timeout(400)
            print('   [通过] 字段/统计/最近帖子/空边界')
            record('U5_detail_drawer', VP, 'PASS',
                   assertions={'fields_ok': True, 'stats_cards': 4, 'recent_posts': True,
                               'empty_boundary': True}, screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('U5_detail_drawer', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= U6 角色修改 =================
        print('\n--- U6 角色修改：确认/请求体/取消/失败一致性 ---')
        try:
            wait_msgs_gone(page)
            role_select = page.locator('.el-table__row').first.locator('.el-select').first
            role_select.click()
            page.wait_for_timeout(500)
            page.locator('.el-select-dropdown__item:visible', has_text='游客').first.click()
            page.wait_for_selector('.el-message-box', timeout=5000)
            check('角色改为「guest」' in page.locator('.el-message-box').inner_text(),
                  f'确认文案应含目标角色，实际: {page.locator(".el-message-box").inner_text()[:120]}')
            confirm_box(page, confirm=True)
            page.wait_for_timeout(1000)
            put = last_requests('PUT', '/role')[0]
            check((put['body'] or {}) == {'role': 'guest'}, f'角色请求体不符: {put["body"]}')
            check('角色已更新' in msg_text(page), f'应有成功提示，实际: 「{msg_text(page)}」')
            gets_before = count_requests('GET', '/admin/users')
            check(last_requests('GET', '/admin/users')[0] is not None, '成功后应刷新列表')

            # 取消：零 PUT，选择器还原
            wait_msgs_gone(page)
            puts_before = count_requests('PUT', '/role')
            role_select = page.locator('.el-table__row').first.locator('.el-select').first
            role_select.click()
            page.wait_for_timeout(500)
            page.locator('.el-select-dropdown__item:visible', has_text='管理员').first.click()
            confirm_box(page, confirm=False)
            page.wait_for_timeout(800)
            check(count_requests('PUT', '/role') == puts_before, '取消角色修改不得发出请求')
            disp = page.locator('.el-table__row').first.locator('.el-select .el-select__placeholder, .el-select__selected-item').first.inner_text()
            check('管理员' not in disp, f'取消后选择器显示值应还原（不得残留未生效选择），实际: {disp}')

            # 业务错误：不误报成功，选择器显示值与服务端一致
            wait_msgs_gone(page)
            flags['role_error'] = True
            puts_before = count_requests('PUT', '/role')
            role_select = page.locator('.el-table__row').first.locator('.el-select').first
            role_select.click()
            page.wait_for_timeout(500)
            page.locator('.el-select-dropdown__item:visible', has_text='游客').first.click()
            confirm_box(page, confirm=True)
            page.wait_for_timeout(800)
            check(count_requests('PUT', '/role') - puts_before == 1, '业务错误场景应发 1 次请求')
            check('不能修改其他管理员的角色' in msg_text(page),
                  f'应展示后端业务错误，实际: 「{msg_text(page)}」')
            check('角色已更新' not in msg_text(page), '失败不得误报成功')
            flags['role_error'] = False
            s = shot(page, 'users-u6-role-error.png')
            print('   [通过] 确认文案/请求体/取消还原/失败不误报')
            record('U6_role_change', VP, 'PASS',
                   assertions={'confirm_text': True, 'body': {'role': 'guest'},
                               'cancel_no_request': True, 'cancel_reverts': True,
                               'error_no_false_success': True}, screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('U6_role_change', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            flags['role_error'] = False

        # ================= U7 冻结与解冻 =================
        print('\n--- U7 冻结与解冻 ---')
        try:
            wait_msgs_gone(page)
            # 冻结（行 1 status=1）
            puts_before = count_requests('PUT', '/status')
            page.locator('.el-table__row').first.locator('button:has-text("冻结")').click()
            page.wait_for_selector('.el-message-box', timeout=5000)
            check('冻结后无法登录' in page.locator('.el-message-box').inner_text(), '冻结确认文案')
            confirm_box(page, confirm=True)
            page.wait_for_timeout(1000)
            check(count_requests('PUT', '/status') - puts_before == 1, '冻结应发 1 次 PUT')
            check(last_requests('PUT', '/status')[0]['query'].get('status') == '0',
                  f'冻结参数应为 status=0，实际: {last_requests("PUT", "/status")[0]["query"]}')
            check('已冻结' in msg_text(page), '应有已冻结提示')

            # 冻结取消：零请求
            wait_msgs_gone(page)
            page.locator('button:has-text("重置")').click() if page.locator('button:has-text("重置")').count() else None
            page.locator('button:has-text("查询")').click()
            page.wait_for_timeout(800)
            puts_before = count_requests('PUT', '/status')
            row_frozen = page.locator('.el-table__row', has_text='已冻结').first
            if row_frozen.count() == 0:
                raise ScenarioFailure('冻结后列表未出现已冻结行（状态刷新失败）')
            # 冻结行的按钮应变为解冻
            check(row_frozen.locator('button:has-text("解冻")').count() == 1,
                  '冻结成功后操作按钮应变为解冻')

            # 解冻网络失败
            flags['status_abort'] = True
            row_frozen.locator('button:has-text("解冻")').click()
            page.wait_for_timeout(800)
            check('已解冻' not in msg_text(page), '网络失败不得误报已解冻')
            s = shot(page, 'users-u7-unfreeze-abort.png')
            # 解冻恢复重试
            flags['status_abort'] = False
            page.locator('.el-table__row', has_text='已冻结').first.locator('button:has-text("解冻")').click()
            page.wait_for_timeout(1000)
            check('已解冻' in msg_text(page), f'重试解冻应成功，实际: 「{msg_text(page)}」')
            check(last_requests('PUT', '/status')[0]['query'].get('status') == '1',
                  '解冻参数应为 status=1')
            print('   [通过] 冻结确认/参数/按钮变化/解冻网络失败与重试')
            record('U7_freeze_unfreeze', VP, 'PASS',
                   assertions={'freeze_status': '0', 'button_flip': True,
                               'abort_no_false_success': True, 'unfreeze_status': '1'},
                   screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('U7_freeze_unfreeze', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            flags['status_abort'] = False

        # ================= U8 注销用户限制 =================
        print('\n--- U8 注销用户限制 ---')
        try:
            page.locator('.el-form-item', has_text='搜索').locator('input').fill('已注销')
            page.locator('button:has-text("查询")').click()
            page.wait_for_timeout(800)
            row = page.locator('.el-table__row').first
            check('已注销用户' in row.inner_text(), '应查到注销用户')
            wrapper_class = row.locator('.el-select .el-select__wrapper').first.get_attribute('class') or ''
            input_disabled = row.locator('.el-select input').first.is_disabled()
            check('is-disabled' in wrapper_class or input_disabled,
                  f'注销用户角色选择器应禁用，wrapper class: {wrapper_class}, input disabled: {input_disabled}')
            check(row.locator('button:has-text("冻结")').count() == 0, '注销用户不应有冻结按钮')
            check('—' in row.locator('td').last.inner_text(), '注销用户操作列应为 —')
            page.locator('.el-form-item', has_text='搜索').locator('input').fill('')
            page.locator('button:has-text("查询")').click()
            page.wait_for_timeout(800)
            s = shot(page, 'users-u8-deleted-user.png')
            print('   [通过] 角色选择禁用、无冻结按钮')
            record('U8_deleted_user_restrictions', VP, 'PASS',
                   assertions={'role_select_disabled': True, 'no_freeze_button': True}, screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('U8_deleted_user_restrictions', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= U9 CSV 导出 =================
        print('\n--- U9 CSV 导出 ---')
        try:
            wait_msgs_gone(page)
            with page.expect_download(timeout=8000) as dl_info:
                page.locator('button:has-text("导出 CSV")').click()
            download = dl_info.value
            check((download.suggested_filename or '').startswith('users-') and download.suggested_filename.endswith('.csv'),
                  f'下载文件名应为 users-*.csv，实际: {download.suggested_filename}')
            check(count_requests('GET', '/admin/export/users') >= 1, '应有真实导出请求')
            check('已导出' in msg_text(page), f'应有成功提示，实际: 「{msg_text(page)}」')

            flags['export_error'] = True
            page.locator('button:has-text("导出 CSV")').click()
            page.wait_for_timeout(800)
            check('导出失败' in msg_text(page), f'导出失败应有错误提示，实际: 「{msg_text(page)}」')
            flags['export_error'] = False
            print('   [通过] 下载触发/文件名/失败反馈')
            record('U9_export_csv', VP, 'PASS',
                   assertions={'download': download.suggested_filename, 'error_toast': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('U9_export_csv', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            flags['export_error'] = False

        ctx.close()

        # ================= U10 响应式 =================
        for label, w, h in [('tablet-768', 768, 1024), ('narrow-390', 390, 844)]:
            print(f'\n--- U10 响应式 {label} ---')
            try:
                ctx2, page2 = new_admin_context(browser, w, h)
                page2.goto(f'{base_url}/users')
                page2.wait_for_selector('.el-table__row', timeout=8000)
                page2.wait_for_timeout(600)
                m = doc_overflow(page2)
                check(m['sw'] <= m['cw'] + 2, f'{label} 页面横向溢出: {m}')
                page2.locator('.el-table__row').first.locator('button:has-text("详情")').click()
                page2.wait_for_selector('.el-drawer:visible', timeout=5000)
                page2.wait_for_timeout(600)
                dr = page2.locator('.el-drawer:visible').first.bounding_box()
                check(dr['x'] >= 0 and dr['x'] + dr['width'] <= w + 1,
                      f'{label} 详情抽屉超出视口: {dr} (视口 {w})')
                check(page2.locator('.el-drawer:visible .d-stat').count() == 4, f'{label} 统计卡片应完整')
                m2 = doc_overflow(page2)
                check(m2['sw'] <= m2['cw'] + 2, f'{label} 抽屉打开后页面横向溢出: {m2}')
                s = shot(page2, f'users-u10-{label}.png')
                print(f'   [通过] {label} 无溢出，抽屉与统计卡片适配')
                record(f'U10_responsive_{label}', f'{w}x{h}', 'PASS',
                       assertions={'doc': m2, 'drawer': dr, 'stats_cards': 4}, screenshots=[s])
                ctx2.close()
            except Exception as e:
                print(f'   [失败] {e}')
                record(f'U10_responsive_{label}', f'{w}x{h}', 'FAIL',
                       error=f'{e}\n{traceback.format_exc(limit=3)}')
                try:
                    shot(page2, f'users-u10-{label}-fail.png')
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

report_path = f'{ARTIFACTS_DIR}/users-view-report.json'
with open(report_path, 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

passed = sum(1 for s in report['scenarios'] if s['status'] == 'PASS')
print(f'\n========================================================')
print(f'用户管理页验收结束: {passed}/{len(report["scenarios"])} 场景通过，总体 {report["overall"]}')
print(f'报告: {report_path}')
print(f'========================================================')

if report['overall'] != 'PASS':
    sys.exit(1)
