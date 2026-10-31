#!/usr/bin/env python3
"""
SchoolWall 管理后台 帖子管理页（PostsView.vue）真实浏览器验收
（独立脚本；静态 dist + 单 Chromium 串行；Mock API，非真实后端联调）

场景：
  A1 初始列表加载（20 条/页、总数、加载态结束）
  A2 空列表状态
  A3 筛选：关键词/状态/类型/精确 ID + 查询与重置的参数契约
  A4 分页：页码切换、每页条数变化
  A5 编辑：空内容校验零请求、正常保存、保存失败弹窗保持与恢复
  A6 单条操作：置顶/设精华/封禁/过审的请求参数与列表刷新、确认框取消零请求
  A7 批量操作：禁用态、多选、确认、部分失败反馈
  A8 精华候选弹窗：加载、设为精华、列表同步
  A9 CSV 导出：筛选范围与 API 契约一致、下载触发、失败提示
  A10 响应式：768 平板与 480 窄屏的表格/弹窗/横向溢出

产物：ci-artifacts/admin-ui/posts-view-report.json + posts-*.png
任一断言失败 -> 场景 FAIL，退出码非零。
"""

import json
import os
import sys
import time
import traceback
import urllib.parse
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

# ---------------------------------------------------------------- Mock 状态
requests_log = []          # {method, path, query, body}
flags = {'empty': False, 'edit_error': False, 'export_error': False}

def log_req(route, body=None):
    u = urllib.parse.urlparse(route.request.url)
    requests_log.append({'method': route.request.method, 'path': u.path,
                         'query': dict(urllib.parse.parse_qsl(u.query)), 'body': body})

def make_post(i):
    return {
        'id': i, 'post_type': ['general', 'second_hand', 'lost_found'][i % 3],
        'category': '校园生活' if i % 2 else '学习考研',
        'content': f'第{i}条帖子：图书馆自习室讨论' if i % 2 else f'第{i}条帖子：二手闲置转让',
        'images': [], 'images_count': 0, 'price': None,
        'status': [1, 0, -1][i % 3],
        'is_pinned': i == 2, 'is_featured': i == 3,
        'author': {'nickname': f'同学{i}', 'id': f'u{i}'},
        'like_count': i, 'comment_count': i % 5, 'view_count': 100 + i,
        'created_at': f'2026-10-{(i % 20) + 1:02d}T08:00:00Z',
    }

ALL_POSTS = [make_post(i) for i in range(1, 46)]

def posts_page(query):
    items = list(ALL_POSTS)
    pid = query.get('post_id')
    if pid:
        items = [p for p in items if p['id'] == int(pid)]
    q = query.get('q')
    if q:
        items = [p for p in items if q in p['content']]
    st = query.get('status')
    if st not in (None, ''):
        items = [p for p in items if p['status'] == int(st)]
    pt = query.get('post_type')
    if pt:
        items = [p for p in items if p['post_type'] == pt]
    if query.get('time_start') or query.get('time_end'):
        pass  # 日期过滤：记录参数即可，夹具时间均在范围内
    total = len(items)
    page = int(query.get('page', 1))
    size = int(query.get('page_size', 20))
    return items[(page - 1) * size: page * size], total

CANDIDATES = [
    dict(make_post(10), is_featured=False),
    dict(make_post(20), is_featured=False),
]

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
    log_req(route, body)

    if path.endswith('/admin/auth/me'):
        return fulfill(route, {'code': 0, 'data': {'id': 'a1', 'username': 'admin',
                       'display_name': '系统管理员', 'role': 'super_admin', 'mfa_enabled': True}})
    if path.endswith('/admin/posts/feature-candidates'):
        return fulfill(route, {'code': 0, 'data': {'items': CANDIDATES}})
    if path.endswith('/admin/posts/batch-status'):
        ids = (body or {}).get('post_ids', [])
        return fulfill(route, {'code': 0, 'data': {
            'succeeded': ids[:1],
            'failed': [{'id': i, 'reason': '帖子状态已变化'} for i in ids[1:]]}})
    if path.endswith('/admin/export/posts'):
        if flags['export_error']:
            return fulfill(route, {'code': 500, 'message': '导出任务失败'}, status=500)
        csv = 'id,content,status\n1,第1条帖子,1\n'
        return route.fulfill(status=200, content_type='text/csv',
                             headers={'Content-Disposition': 'attachment; filename="posts.csv"'},
                             body=csv)
    if '/admin/posts/' in path and req.method == 'PUT' and path.rstrip('/').endswith('/status'):
        return fulfill(route, {'code': 0, 'data': {'status': int(query.get('status', 0))}})
    if '/admin/posts/' in path and req.method == 'PUT' and path.rstrip('/').endswith('/pin'):
        return fulfill(route, {'code': 0, 'data': {'is_pinned': (body or {}).get('pinned', False)}})
    if '/admin/posts/' in path and req.method == 'PUT' and path.rstrip('/').endswith('/featured'):
        return fulfill(route, {'code': 0, 'data': {'is_featured': (body or {}).get('pinned', False)}})
    if '/admin/posts/' in path and req.method == 'PUT':
        if flags['edit_error']:
            return fulfill(route, {'code': 400, 'message': '内容包含敏感词，请修改后保存'})
        return fulfill(route, {'code': 0, 'data': {'saved': True}})
    if path.endswith('/admin/posts'):
        if flags['empty']:
            return fulfill(route, {'code': 0, 'data': {'items': [], 'total': 0, 'page': 1, 'page_size': 20}})
        items, total = posts_page(query)
        return fulfill(route, {'code': 0, 'data': {'items': items, 'total': total,
                       'page': int(query.get('page', 1)), 'page_size': int(query.get('page_size', 20))}})
    # 其它管理接口兜底
    return fulfill(route, {'code': 0, 'message': 'ok', 'data': {'items': [], 'total': 0}})

# ---------------------------------------------------------------- 工具
class ScenarioFailure(Exception):
    pass

def check(cond, msg):
    if not cond:
        raise ScenarioFailure(msg)

report = {
    'task': 'admin PostsView.vue browser acceptance',
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

def last_requests(method=None, path_suffix=None, n=1):
    out = [r for r in requests_log
           if (method is None or r['method'] == method) and (path_suffix is None or r['path'].endswith(path_suffix))]
    return out[-n:] if n else out

def count_requests(method, path_suffix):
    return sum(1 for r in requests_log if r['method'] == method and r['path'].endswith(path_suffix))

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
    # 关闭可能残留的下拉浮层，避免遮挡后续交互
    page.keyboard.press('Escape')
    page.wait_for_timeout(200)

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

exit_code = 0
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx, page = new_admin_context(browser, 1280, 800)
        VP = '1280x800'

        # ================= A1 初始加载 =================
        print('\n--- A1 初始列表加载 ---')
        try:
            page.goto(route_url(base_url, '/posts'))
            page.wait_for_selector('.el-table__row', timeout=8000)
            page.wait_for_timeout(600)
            check(page.locator('.el-table__row').count() == 20, '首页应渲染 20 行')
            check('共 45 条' in page.locator('.el-pagination').inner_text(), '分页总数应为 45')
            check(page.locator('.el-loading-mask').count() == 0, '加载态应结束')
            s = shot(page, 'posts-a1-loaded.png')
            print('   [通过] 20 行 / 共 45 条 / 加载态结束')
            record('A1_initial_load', VP, 'PASS',
                   assertions={'rows': 20, 'total': 45}, screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('A1_initial_load', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= A2 空列表 =================
        print('\n--- A2 空列表状态 ---')
        try:
            flags['empty'] = True
            page.locator('button:has-text("查询")').click()
            page.wait_for_timeout(800)
            check(page.locator('.el-table__row').count() == 0, '空列表不应有数据行')
            check(page.locator('.el-table__empty-text').is_visible(), '应显示空态提示')
            flags['empty'] = False
            page.locator('button:has-text("查询")').click()
            page.wait_for_selector('.el-table__row', timeout=5000)
            print('   [通过] 空态提示正确，恢复查询正常')
            record('A2_empty_state', VP, 'PASS', assertions={'empty_text': True, 'recover': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('A2_empty_state', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            flags['empty'] = False

        # ================= A3 筛选与重置 =================
        print('\n--- A3 筛选参数契约与重置 ---')
        try:
            page.locator('.el-form-item', has_text='关键词').locator('input').fill('自习')
            page.locator('button:has-text("查询")').click()
            page.wait_for_timeout(800)
            q = last_requests('GET', '/admin/posts')[0]['query']
            check(q.get('q') == '自习' and q.get('page') == '1',
                  f'关键词查询应带 q=自习 且 page=1，实际: {q}')
            check(page.locator('.el-table__row').count() > 0, '关键词筛选应有结果')

            select_option(page, '状态', '待审核')
            page.locator('button:has-text("查询")').click()
            page.wait_for_timeout(800)
            q = last_requests('GET', '/admin/posts')[0]['query']
            check(q.get('status') == '0', f'状态筛选应带 status=0，实际: {q}')

            select_option(page, '类型', '失物招领')
            page.locator('button:has-text("查询")').click()
            page.wait_for_timeout(800)
            q = last_requests('GET', '/admin/posts')[0]['query']
            check(q.get('post_type') == 'lost_found', f'类型筛选应带 post_type=lost_found，实际: {q}')

            # 精确 ID 单独验证（先重置，避免与状态/类型/关键词条件叠加）
            page.locator('button:has-text("重置")').click()
            page.wait_for_timeout(800)
            page.locator('.el-form-item', has_text='帖子 ID').locator('input').fill('5')
            page.locator('button:has-text("查询")').click()
            page.wait_for_timeout(800)
            q = last_requests('GET', '/admin/posts')[0]['query']
            check(q.get('post_id') == '5', f'ID 筛选应带 post_id=5，实际: {q}')
            check(page.locator('.el-table__row').count() == 1,
                  f'精确 ID 应只返回 1 行，实际 {page.locator(".el-table__row").count()} 行')

            page.locator('button:has-text("重置")').click()
            page.wait_for_timeout(800)
            q = last_requests('GET', '/admin/posts')[0]['query']
            check('q' not in q and 'status' not in q and 'post_type' not in q and 'post_id' not in q,
                  f'重置后参数应为空，实际: {q}')
            check(q.get('page') == '1', f'重置后应回到第 1 页，实际: {q}')
            s = shot(page, 'posts-a3-filters.png')
            print(f'   [通过] 关键词/状态/类型/ID 参数正确，重置清空并回第 1 页')
            record('A3_filters_reset', VP, 'PASS',
                   assertions={'keyword_q': '自习', 'status': '0', 'post_type': 'lost_found',
                               'post_id': '5', 'reset_clean': True}, screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('A3_filters_reset', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= A4 分页 =================
        print('\n--- A4 分页与每页条数 ---')
        try:
            page.locator('.el-pager li.number', has_text='2').first.click()
            page.wait_for_timeout(800)
            q = last_requests('GET', '/admin/posts')[0]['query']
            check(q.get('page') == '2', f'翻页应带 page=2，实际: {q}')
            first_id_page2 = page.locator('.el-table__row').first.locator('td').nth(1).inner_text().strip()
            check(first_id_page2 == '21', f'第 2 页首行应为 ID=21，实际 {first_id_page2}')

            page.locator('.el-pagination .el-select').click()
            page.wait_for_timeout(500)
            page.locator('.el-select-dropdown__item:visible', has_text='10条/页').first.click()
            page.wait_for_timeout(800)
            q = last_requests('GET', '/admin/posts')[0]['query']
            check(q.get('page_size') == '10', f'每页条数应为 10，实际: {q}')
            check(page.locator('.el-table__row').count() == 10, '应渲染 10 行')
            s = shot(page, 'posts-a4-pagination.png')
            print('   [通过] page=2 参数正确，每页 10 条生效')
            record('A4_pagination', VP, 'PASS',
                   assertions={'page2_param': '2', 'page2_first_id': '21', 'size10_rows': 10},
                   screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('A4_pagination', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # 回到 20 条/页第一页，便于后续行级操作
        page.locator('.el-pagination .el-select').click()
        page.wait_for_timeout(500)
        page.locator('.el-select-dropdown__item:visible', has_text='20条/页').first.click()
        page.wait_for_timeout(800)
        page.locator('.el-pager li.number', has_text='1').first.click()
        page.wait_for_timeout(800)

        # ================= A5 编辑 =================
        print('\n--- A5 编辑：空校验/保存/失败恢复 ---')
        try:
            page.locator('.el-table__row').first.locator('button:has-text("编辑")').click()
            page.wait_for_selector('.el-dialog', timeout=5000)
            ta = page.locator('.el-dialog textarea')
            ta.fill('')
            puts_before = count_requests('PUT', '/admin/posts/1')
            page.locator('.el-dialog button:has-text("保存")').click()
            page.wait_for_timeout(600)
            check(count_requests('PUT', '/admin/posts/1') == puts_before, '空内容不得发出保存请求')
            check('内容不能为空' in msg_text(page), f'应有空校验提示，实际: 「{msg_text(page)}」')
            check(page.locator('.el-dialog:visible').count() >= 1, '校验失败弹窗应保持打开')

            ta.fill('修改后的自习室新规讨论内容')
            page.locator('.el-dialog button:has-text("保存")').click()
            page.wait_for_timeout(1000)
            put = last_requests('PUT', '/admin/posts/1')[0]
            check((put['body'] or {}).get('content') == '修改后的自习室新规讨论内容',
                  f'保存请求体不符: {put["body"]}')
            check('已保存' in msg_text(page), '应有保存成功提示')
            page.wait_for_timeout(400)
            check(page.locator('.el-dialog:visible').count() == 0,
                  '保存成功后弹窗应关闭')

            # 保存失败：弹窗保持、错误提示、按钮恢复
            flags['edit_error'] = True
            page.locator('.el-table__row').first.locator('button:has-text("编辑")').click()
            page.wait_for_selector('.el-dialog textarea', timeout=5000)
            page.locator('.el-dialog button:has-text("保存")').click()
            page.wait_for_timeout(800)
            check('内容包含敏感词，请修改后保存' in msg_text(page),
                  f'应展示后端错误，实际: 「{msg_text(page)}」')
            check(page.locator('.el-dialog:visible').count() >= 1, '保存失败后弹窗应保持打开')
            btn_class = page.locator('.el-dialog button:has-text("保存")').get_attribute('class') or ''
            check('is-loading' not in btn_class, '失败后保存按钮应解除 loading')
            s = shot(page, 'posts-a5-edit-error.png')

            flags['edit_error'] = False
            page.locator('.el-dialog button:has-text("保存")').click()
            page.wait_for_timeout(1000)
            check('已保存' in msg_text(page), '重试保存应成功')
            print('   [通过] 空校验零请求、正常保存、失败保持+恢复重试')
            record('A5_edit_flow', VP, 'PASS',
                   assertions={'empty_no_request': True, 'save_body_ok': True,
                               'error_dialog_kept': True, 'retry_success': True}, screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('A5_edit_flow', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            flags['edit_error'] = False

        # ================= A6 单条操作与取消 =================
        print('\n--- A6 置顶/精华/封禁/过审/取消 ---')
        try:
            # 置顶（行 1，is_pinned=False）
            pins_before = count_requests('PUT', '/admin/posts/1/pin')
            page.locator('.el-table__row').first.locator('button:has-text("置顶")').click()
            page.wait_for_timeout(1000)
            check(count_requests('PUT', '/admin/posts/1/pin') - pins_before == 1, '置顶应发 1 次 PUT pin')
            check((last_requests('PUT', '/admin/posts/1/pin')[0]['body'] or {}).get('pinned') is True,
                  f'置顶请求体应为 {{"pinned": true}}，实际: {last_requests("PUT", "/admin/posts/1/pin")[0]["body"]}')

            # 设精华（行 1，is_featured=False）
            feats_before = count_requests('PUT', '/admin/posts/1/featured')
            page.locator('.el-table__row').first.locator('button:has-text("设精华")').click()
            page.wait_for_timeout(1000)
            check(count_requests('PUT', '/admin/posts/1/featured') - feats_before == 1, '设精华应发 1 次 PUT featured')
            check((last_requests('PUT', '/admin/posts/1/featured')[0]['body'] or {}).get('pinned') is True,
                  '精华请求体应复用 {pinned: true}（与后端 PinRequest 契约一致）')

            # 封禁（行 3，status=1 → 封禁按钮）确认
            st_before = count_requests('PUT', '/admin/posts/3/status')
            page.locator('.el-table__row').nth(2).locator('button:has-text("封禁")').click()
            confirm_box(page, confirm=True)
            page.wait_for_timeout(1000)
            check(count_requests('PUT', '/admin/posts/3/status') - st_before == 1, '确认后应发 1 次 PUT status')
            check(last_requests('PUT', '/admin/posts/3/status')[0]['query'].get('status') == '-1',
                  f'封禁参数应为 status=-1，实际: {last_requests("PUT", "/admin/posts/3/status")[0]["query"]}')

            # 取消确认：零请求、无错误提示
            page.locator('.el-table__row').nth(2).locator('button:has-text("封禁")').click()
            st_before = count_requests('PUT', '/admin/posts/3/status')
            confirm_box(page, confirm=False)
            page.wait_for_timeout(600)
            check(count_requests('PUT', '/admin/posts/3/status') == st_before, '取消确认不得发出请求')

            # 过审（行 1，status=0）
            page.locator('.el-table__row').nth(0).locator('button:has-text("过审")').click()
            confirm_box(page, confirm=True)
            page.wait_for_timeout(1000)
            check(last_requests('PUT', '/admin/posts/1/status')[0]['query'].get('status') == '1',
                  '过审参数应为 status=1')
            gets_before = count_requests('GET', '/admin/posts')
            print('   [通过] 置顶/精华/封禁参数正确，取消零请求，过审 status=1')
            record('A6_row_actions', VP, 'PASS',
                   assertions={'pin_body': {'pinned': True}, 'featured_body': {'pinned': True},
                               'ban_status': '-1', 'approve_status': '1', 'cancel_no_request': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('A6_row_actions', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= A7 批量操作 =================
        print('\n--- A7 批量操作：禁用/多选/部分失败 ---')
        try:
            batch_btn = page.locator('button:has-text("批量封禁")')
            check(batch_btn.get_attribute('class').find('is-disabled') >= 0 or batch_btn.is_disabled(),
                  '未选中时批量按钮应禁用')
            page.locator('.el-table__row').nth(0).locator('.el-checkbox').click()
            page.locator('.el-table__row').nth(1).locator('.el-checkbox').click()
            page.wait_for_timeout(400)
            check('已选 2 条' in page.locator('.selected-tip').inner_text(), '应显示已选 2 条')
            check(not batch_btn.is_disabled(), '选中后批量按钮应启用')
            batch_btn.click()
            confirm_box(page, confirm=True)
            page.wait_for_timeout(1000)
            post = last_requests('POST', '/admin/posts/batch-status')[0]
            check((post['body'] or {}).get('post_ids') == [1, 2] and post['body'].get('status') == -1,
                  f'批量请求体不符: {post["body"]}')
            check('成功 1 条，失败 1 条' in msg_text(page),
                  f'部分失败应如实反馈，实际: 「{msg_text(page)}」')
            s = shot(page, 'posts-a7-batch.png')
            print('   [通过] 禁用→多选→确认→批量体正确→部分失败反馈')
            record('A7_batch_ops', VP, 'PASS',
                   assertions={'disabled_when_empty': True, 'body': {'post_ids': [1, 2], 'status': -1},
                               'partial_feedback': '成功 1 条，失败 1 条'}, screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('A7_batch_ops', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= A8 精华候选 =================
        print('\n--- A8 精华候选弹窗 ---')
        try:
            page.locator('button:has-text("精华候选")').click()
            page.wait_for_selector('.el-dialog .el-table__row', timeout=5000)
            check(page.locator('.el-dialog .el-table__row').count() == 2, '候选弹窗应渲染 2 行')
            feats_before = count_requests('PUT', '/admin/posts/10/featured')
            page.locator('.el-dialog .el-table__row').first.locator('button:has-text("设为精华")').click()
            page.wait_for_timeout(1000)
            check(count_requests('PUT', '/admin/posts/10/featured') - feats_before == 1,
                  '设为精华应发 1 次 PUT featured')
            check(page.locator('.el-dialog .el-table__row').count() == 1, '设精后候选应移出弹窗列表')
            page.locator('.el-dialog button:has-text("关闭")').click()
            page.wait_for_timeout(400)
            print('   [通过] 候选加载、设为精华、弹窗列表同步')
            record('A8_feature_candidates', VP, 'PASS',
                   assertions={'candidates': 2, 'after_adopt': 1})
        except Exception as e:
            print(f'   [失败] {e}')
            record('A8_feature_candidates', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= A9 CSV 导出 =================
        print('\n--- A9 CSV 导出契约与失败处理 ---')
        try:
            page.locator('.el-form-item', has_text='关键词').locator('input').fill('自习')
            with page.expect_download(timeout=8000) as dl_info:
                page.locator('button:has-text("导出 CSV")').click()
            download = dl_info.value
            check('posts-' in (download.suggested_filename or '') and download.suggested_filename.endswith('.csv'),
                  f'下载文件名应为 posts-*.csv，实际: {download.suggested_filename}')
            exp = last_requests('GET', '/admin/export/posts')[0]
            check(exp['query'].get('q') == '自习',
                  f'导出应带当前关键词筛选 q=自习，实际: {exp["query"]}')
            check('post_type' not in exp['query'] and 'post_id' not in exp['query'],
                  f'导出参数应与 API 契约一致（仅 status/q），实际: {exp["query"]}')
            check('已导出' in msg_text(page), f'应有导出成功提示，实际: 「{msg_text(page)}」')

            flags['export_error'] = True
            page.locator('button:has-text("导出 CSV")').click()
            page.wait_for_timeout(800)
            check('导出失败' in msg_text(page) or '导出任务失败' in msg_text(page),
                  f'导出失败应有错误提示，实际: 「{msg_text(page)}」')
            flags['export_error'] = False
            s = shot(page, 'posts-a9-export.png')
            print('   [通过] 下载触发、筛选范围与 API 契约一致、失败提示')
            record('A9_export_csv', VP, 'PASS',
                   assertions={'download': download.suggested_filename, 'export_query': exp['query'],
                               'error_toast': True}, screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('A9_export_csv', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            flags['export_error'] = False

        ctx.close()

        # ================= A10 响应式 =================
        for label, w, h in [('tablet-768', 768, 1024), ('narrow-480', 480, 800)]:
            print(f'\n--- A10 响应式 {label} ---')
            try:
                ctx2, page2 = new_admin_context(browser, w, h)
                page2.goto(route_url(base_url, '/posts'))
                page2.wait_for_selector('.el-table__row', timeout=8000)
                page2.wait_for_timeout(600)
                m = doc_overflow(page2)
                check(m['sw'] <= m['cw'] + 2, f'{label} 页面横向溢出: {m}')
                # 编辑弹窗（560px）与精华候选弹窗（640px）在窄屏是否溢出
                page2.locator('.el-table__row').first.locator('button:has-text("编辑")').click()
                page2.wait_for_selector('.el-dialog', timeout=5000)
                dlg = page2.locator('.el-dialog:visible').first.bounding_box()
                check(dlg['x'] >= 0 and dlg['x'] + dlg['width'] <= w + 1,
                      f'{label} 编辑弹窗超出视口: {dlg} (视口 {w})')
                page2.locator('.el-dialog button:has-text("取消")').click()
                page2.wait_for_timeout(400)
                page2.locator('button:has-text("精华候选")').click()
                page2.wait_for_selector('.el-dialog .el-table__row', timeout=5000)
                dlg2 = page2.locator('.el-dialog:visible').first.bounding_box()
                check(dlg2['x'] >= 0 and dlg2['x'] + dlg2['width'] <= w + 1,
                      f'{label} 精华候选弹窗超出视口: {dlg2} (视口 {w})')
                m2 = doc_overflow(page2)
                s = shot(page2, f'posts-a10-{label}.png')
                print(f'   [通过] {label} 无横向溢出，弹窗适配')
                record(f'A10_responsive_{label}', f'{w}x{h}', 'PASS',
                       assertions={'doc': m2, 'edit_dialog': dlg, 'candidates_dialog': dlg2},
                       screenshots=[s])
                ctx2.close()
            except Exception as e:
                print(f'   [失败] {e}')
                record(f'A10_responsive_{label}', f'{w}x{h}', 'FAIL',
                       error=f'{e}\n{traceback.format_exc(limit=3)}')
                try:
                    shot(page2, f'posts-a10-{label}-fail.png')
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

report_path = f'{ARTIFACTS_DIR}/posts-view-report.json'
with open(report_path, 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

passed = sum(1 for s in report['scenarios'] if s['status'] == 'PASS')
print(f'\n========================================================')
print(f'帖子管理页验收结束: {passed}/{len(report["scenarios"])} 场景通过，总体 {report["overall"]}')
print(f'报告: {report_path}')
print(f'========================================================')

if report['overall'] != 'PASS':
    sys.exit(1)
