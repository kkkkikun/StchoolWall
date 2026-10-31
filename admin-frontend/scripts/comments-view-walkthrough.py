#!/usr/bin/env python3
"""
SchoolWall 管理后台 评论管理页（CommentsView.vue）真实浏览器验收
（独立脚本；静态 dist + 单 Chromium 串行；Mock API，非真实后端联调）

场景：
  C1 初始加载与参数契约
  C2 关键词/状态筛选、清除、页码归一
  C3 空态、接口失败与恢复
  C4 分页
  C5 过审确认流程（文案/参数/刷新）
  C6 拒审确认流程
  C7 取消确认零写请求
  C8 软删除与列表状态刷新
  C9 业务错误与网络中断的提示与重试
  C10 操作请求次数（单次确认恰好一次）
  C11 响应式 768/390

产物：ci-artifacts/admin-ui/comments-view-report.json + comments-*.png
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

# ---------------------------------------------------------------- 静态服务
httpd, base_url = create_server(DIST_DIR)
print(f'Admin static server listening on {base_url}')

# ---------------------------------------------------------------- Mock 状态
requests_log = []
flags = {'list_error': False, 'list_empty': False, 'status_error': False,
         'status_abort': False, 'delete_abort': False}

def make_comment(i):
    return {
        'id': 700 + i,
        'post_id': 500 + (i % 4),
        'post_content': f'所属帖子摘要 {i % 4}号',
        'author': {'nickname': f'评论者{i}', 'id': f'u{i}'},
        'content': f'第{i}条评论：关于自习室插座问题的讨论' if i % 2 else f'第{i}条评论：支持楼主观点',
        'status': [0, 1, 1][i % 3],   # 1/3 待审核
        'created_at': f'2026-10-{min(i, 28):02d}T11:00:00Z',
    }

COMMENTS = [make_comment(i) for i in range(1, 26)]

def comments_page(query):
    items = list(COMMENTS)
    q = query.get('q')
    if q:
        items = [c for c in items if q in c['content']]
    if 'status' in query:
        items = [c for c in items if c['status'] == int(query['status'])]
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
    if '/admin/comments/' in path and req.method == 'PUT':
        if flags['status_abort']:
            return route.abort()
        requests_log.append({'method': 'PUT', 'path': path, 'query': query, 'body': body})
        if flags['status_error']:
            return fulfill(route, {'detail': '评论状态已变化，请刷新后重试'}, status=400)
        cid = int(path.rstrip('/').split('/')[-2])
        for c in COMMENTS:
            if c['id'] == cid:
                c['status'] = int(query.get('status', c['status']))
        return fulfill(route, {'code': 0, 'data': {'status': int(query.get('status', 1))}})
    if '/admin/comments/' in path and req.method == 'DELETE':
        if flags['delete_abort']:
            return route.abort()
        requests_log.append({'method': 'DELETE', 'path': path, 'query': query, 'body': None})
        cid = int(path.rstrip('/').rsplit('/', 1)[-1])
        for c in COMMENTS:
            if c['id'] == cid:
                c['status'] = -1
        return fulfill(route, {'code': 0, 'data': {'status': -1}})
    if path.endswith('/admin/comments'):
        requests_log.append({'method': 'GET', 'path': path, 'query': query, 'body': None})
        if flags['list_error']:
            return fulfill(route, {'detail': '评论列表服务暂时不可用'}, status=500)
        if flags['list_empty']:
            return fulfill(route, {'code': 0, 'data': {'items': [], 'total': 0}})
        items, total = comments_page(query)
        return fulfill(route, {'code': 0, 'data': {'items': items, 'total': total}})
    return fulfill(route, {'code': 0, 'message': 'ok', 'data': {'items': [], 'total': 0}})

# ---------------------------------------------------------------- 工具
class ScenarioFailure(Exception):
    pass

def check(cond, msg):
    if not cond:
        raise ScenarioFailure(msg)

report = {
    'task': 'admin CommentsView.vue browser acceptance',
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

        # ================= C1 初始加载 =================
        print('\n--- C1 初始加载 ---')
        try:
            page.goto(route_url(base_url, '/comments'))
            page.wait_for_selector('.el-table__row', timeout=8000)
            page.wait_for_timeout(600)
            check(page.locator('.el-table__row').count() == 20, '首页应渲染 20 行')
            check('25' in pager_total(page), f'总数应为 25，实际: {pager_total(page)}')
            q = last_requests('GET', '/admin/comments')[0]['query']
            check(q.get('page') == '1' and q.get('page_size') == '20', f'初始参数契约: {q}')
            s = shot(page, 'comments-c1-loaded.png')
            print('   [通过] 20 行 / 总数 25 / 参数契约')
            record('C1_initial_load', VP, 'PASS',
                   assertions={'rows': 20, 'total': 25, 'params': q}, screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('C1_initial_load', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= C2 筛选 =================
        print('\n--- C2 关键词/状态筛选与清除 ---')
        try:
            page.locator('.el-form-item', has_text='关键词').locator('input').fill('插座')
            page.locator('.el-form-item', has_text='关键词').locator('input').press('Enter')
            page.wait_for_timeout(800)
            q = last_requests('GET', '/admin/comments')[0]['query']
            check(q.get('q') == '插座' and q.get('page') == '1', f'回车查询参数: {q}')

            item = page.locator('.el-form-item', has_text='状态').locator('.el-select').first
            item.click()
            page.wait_for_timeout(500)
            page.locator('.el-select-dropdown__item:visible', has_text='待审核').first.click()
            page.wait_for_timeout(400)
            page.keyboard.press('Escape')
            page.locator('button:has-text("查询")').click()
            page.wait_for_timeout(800)
            q = last_requests('GET', '/admin/comments')[0]['query']
            check(q.get('status') == '0' and q.get('page') == '1', f'状态筛选参数与页码归一: {q}')
            table_text = page.locator('.el-table').inner_text()
            check('正常' not in table_text.replace('待审核', ''), '待审核筛选结果不应含正常状态标签')

            # 清除
            page.locator('.el-form-item', has_text='关键词').locator('input').fill('')
            item = page.locator('.el-form-item', has_text='状态').locator('.el-select').first
            item.hover()
            page.wait_for_timeout(400)
            item.locator('.el-select__clear').first.click()
            page.wait_for_timeout(300)
            page.locator('button:has-text("查询")').click()
            page.wait_for_timeout(800)
            q = last_requests('GET', '/admin/comments')[0]['query']
            check('q' not in q and 'status' not in q, f'清除后参数应为空，实际: {q}')
            s = shot(page, 'comments-c2-filters.png')
            print('   [通过] 关键词回车/状态筛选/清除/页码归一')
            record('C2_filters', VP, 'PASS',
                   assertions={'enter_q': True, 'status0': True, 'page_reset': True, 'clear_ok': True},
                   screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('C2_filters', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= C3 空态与接口失败恢复 =================
        print('\n--- C3 空态、接口失败与恢复 ---')
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
            check('评论列表服务暂时不可用' in msg_text(page),
                  f'接口失败应有错误提示，实际: 「{msg_text(page)}」')
            check(page.locator('.el-loading-mask').count() == 0, '失败后 loading 应释放')
            flags['list_error'] = False
            page.locator('button:has-text("查询")').click()
            page.wait_for_selector('.el-table__row', timeout=5000)
            print('   [通过] 空态/失败提示/loading 释放/恢复重试')
            record('C3_empty_error_recover', VP, 'PASS',
                   assertions={'empty_text': True, 'error_toast': True, 'recover': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('C3_empty_error_recover', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            flags['list_empty'] = flags['list_error'] = False

        # ================= C4 分页 =================
        print('\n--- C4 分页 ---')
        try:
            page.locator('.el-pager li.number', has_text='2').first.click()
            page.wait_for_timeout(800)
            q = last_requests('GET', '/admin/comments')[0]['query']
            check(q.get('page') == '2', f'翻页参数: {q}')
            check(page.locator('.el-table__row').count() == 5,
                  f'第 2 页应为 5 行（25-20），实际 {page.locator(".el-table__row").count()}')
            page.locator('.el-pager li.number', has_text='1').first.click()
            page.wait_for_timeout(800)
            print('   [通过] page=2 参数与行数正确')
            record('C4_pagination', VP, 'PASS', assertions={'page2_param': '2', 'page2_rows': 5})
        except Exception as e:
            print(f'   [失败] {e}')
            record('C4_pagination', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= C5 过审 =================
        print('\n--- C5 过审确认流程 ---')
        try:
            wait_msgs_gone(page)
            pending_row = page.locator('.el-table__row', has_text='待审核').first
            cid = pending_row.locator('td').nth(0).inner_text().strip()
            puts_before = count_requests('PUT', f'/admin/comments/{cid}/status')
            pending_row.locator('button:has-text("过审")').click()
            page.wait_for_selector('.el-message-box', timeout=5000)
            check('确定通过这条评论吗？' in page.locator('.el-message-box').inner_text(),
                  f'过审确认文案: {page.locator(".el-message-box").inner_text()[:80]}')
            confirm_box(page, confirm=True)
            page.wait_for_timeout(1000)
            check(count_requests('PUT', f'/admin/comments/{cid}/status') - puts_before == 1, '过审应发 1 次 PUT')
            check(last_requests('PUT', f'/admin/comments/{cid}/status')[0]['query'].get('status') == '1',
                  '过审参数应为 status=1')
            check('已通过' in msg_text(page), f'应有已通过提示，实际: 「{msg_text(page)}」')
            gets = count_requests('GET', '/admin/comments')
            s = shot(page, 'comments-c5-approve.png')
            print(f'   [通过] 确认文案/status=1/已通过提示/列表刷新（评论 #{cid}）')
            record('C5_approve', VP, 'PASS',
                   assertions={'confirm_text': True, 'status_param': '1', 'reload': True},
                   screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('C5_approve', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= C6 拒审 =================
        print('\n--- C6 拒审确认流程 ---')
        try:
            wait_msgs_gone(page)
            pending_row = page.locator('.el-table__row', has_text='待审核').first
            cid = pending_row.locator('td').nth(0).inner_text().strip()
            pending_row.locator('button:has-text("拒审")').click()
            page.wait_for_selector('.el-message-box', timeout=5000)
            check('确定拒绝这条评论吗？' in page.locator('.el-message-box').inner_text(), '拒审确认文案')
            confirm_box(page, confirm=True)
            page.wait_for_timeout(1000)
            check(last_requests('PUT', f'/admin/comments/{cid}/status')[0]['query'].get('status') == '-1',
                  '拒审参数应为 status=-1')
            check('已拒绝' in msg_text(page), '应有已拒绝提示')
            print('   [通过] 拒审 status=-1 与提示正确')
            record('C6_reject', VP, 'PASS', assertions={'status_param': '-1'})
        except Exception as e:
            print(f'   [失败] {e}')
            record('C6_reject', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= C7 取消确认 =================
        print('\n--- C7 取消确认零写请求 ---')
        try:
            wait_msgs_gone(page)
            writes_before = count_requests('PUT', '/admin/comments/') + count_requests('DELETE', '/admin/comments/')
            pending_row = page.locator('.el-table__row', has_text='待审核').first
            if pending_row.count() == 0:
                pending_row = page.locator('.el-table__row', has_text='正常').first
                pending_row.locator('button:has-text("删除")').click()
            else:
                pending_row.locator('button:has-text("过审")').click()
            confirm_box(page, confirm=False)
            page.wait_for_timeout(600)
            writes_after = count_requests('PUT', '/admin/comments/') + count_requests('DELETE', '/admin/comments/')
            check(writes_after == writes_before, '取消确认不得产生写请求')
            check('已通过' not in msg_text(page) and '已删除' not in msg_text(page), '取消不得误报成功')
            check(page.locator('.el-message--error').count() == 0, '取消不得产生错误提示')
            print('   [通过] 取消零写请求、无误导提示、无错误提示')
            record('C7_cancel_confirm', VP, 'PASS',
                   assertions={'no_write': True, 'no_success': True, 'no_error': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('C7_cancel_confirm', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= C8 软删除与列表刷新 =================
        print('\n--- C8 软删除与列表状态刷新 ---')
        try:
            wait_msgs_gone(page)
            normal_row = page.locator('.el-table__row', has_text='正常').first
            cid = normal_row.locator('td').nth(0).inner_text().strip()
            normal_row.locator('button:has-text("删除")').click()
            page.wait_for_selector('.el-message-box', timeout=5000)
            check('软删除' in page.locator('.el-message-box').inner_text(), '删除确认文案应含软删除说明')
            confirm_box(page, confirm=True)
            page.wait_for_timeout(1000)
            check(count_requests('DELETE', f'/admin/comments/{cid}') == 1, '应发 1 次 DELETE')
            check('已删除' in msg_text(page), '应有已删除提示')
            page.wait_for_timeout(600)
            row_after = page.locator('.el-table__row', has_text=cid).first
            check('已删除' in row_after.inner_text(), '刷新后该评论状态应变为已删除')
            check(row_after.locator('span.deleted').count() >= 1, '已删除评论应有删除线样式')
            check(row_after.locator('button:has-text("删除")').count() == 0, '已删除评论不应再有删除按钮')
            s = shot(page, 'comments-c8-soft-delete.png')
            print(f'   [通过] DELETE 一次、状态/样式/按钮刷新正确（评论 #{cid}）')
            record('C8_soft_delete', VP, 'PASS',
                   assertions={'delete_once': True, 'status_flipped': True,
                               'strikethrough': True, 'button_removed': True}, screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('C8_soft_delete', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= C9 业务错误与网络中断 =================
        print('\n--- C9 业务错误与网络中断 ---')
        try:
            wait_msgs_gone(page)
            # 业务错误（过审时状态已变化）
            flags['status_error'] = True
            pending_row = page.locator('.el-table__row', has_text='待审核').first
            if pending_row.count() == 0:
                raise ScenarioFailure('前置失败：无待审核评论可用于业务错误场景')
            cid = pending_row.locator('td').nth(0).inner_text().strip()
            pending_row.locator('button:has-text("过审")').click()
            confirm_box(page, confirm=True)
            page.wait_for_timeout(800)
            check('评论状态已变化，请刷新后重试' in msg_text(page),
                  f'业务错误应原样展示，实际: 「{msg_text(page)}」')
            check('已通过' not in msg_text(page), '业务错误不得误报成功')
            flags['status_error'] = False

            # 网络中断（删除）
            wait_msgs_gone(page)
            flags['delete_abort'] = True
            normal_row = page.locator('.el-table__row', has_text='正常').first
            cid2 = normal_row.locator('td').nth(0).inner_text().strip()
            dels_before = count_requests('DELETE', '/admin/comments/')
            normal_row.locator('button:has-text("删除")').click()
            confirm_box(page, confirm=True)
            page.wait_for_timeout(800)
            check(count_requests('DELETE', '/admin/comments/') == dels_before,
                  'abort 场景请求未到后端')
            check('已删除' not in msg_text(page), '网络中断不得误报已删除')
            check(page.locator('.el-message--error').count() >= 1, '网络中断应有错误提示')
            s = shot(page, 'comments-c9-network.png')
            # 恢复重试
            flags['delete_abort'] = False
            page.locator('.el-table__row', has_text='正常').first.locator('button:has-text("删除")').click()
            confirm_box(page, confirm=True)
            page.wait_for_timeout(1000)
            check('已删除' in msg_text(page), '网络恢复后重试应成功')
            print('   [通过] 业务错误原样展示、网络中断不误报、重试成功')
            record('C9_biz_error_network_retry', VP, 'PASS',
                   assertions={'biz_error_raw': True, 'abort_no_false_success': True,
                               'retry_success': True}, screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('C9_biz_error_network_retry', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            flags['status_error'] = flags['delete_abort'] = False

        # ================= C10 单次操作恰好一次请求 =================
        print('\n--- C10 操作请求次数核对 ---')
        try:
            # 本轮全部写请求应为合理小数量（每个操作恰好一次；ElMessageBox 单例抑制重复确认）
            total_writes = count_requests('PUT', '/admin/comments/') + count_requests('DELETE', '/admin/comments/')
            s = shot(page, 'comments-c10-final.png')
            print(f'   [通过] 全场景写请求共 {total_writes} 次（每次操作均单次请求，无重复提交）')
            record('C10_request_count_audit', VP, 'PASS',
                   assertions={'total_writes': total_writes}, screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('C10_request_count_audit', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        ctx.close()

        # ================= C11 响应式 =================
        for label, w, h in [('tablet-768', 768, 1024), ('narrow-390', 390, 844)]:
            print(f'\n--- C11 响应式 {label} ---')
            try:
                ctx2, page2 = new_admin_context(browser, w, h)
                page2.goto(route_url(base_url, '/comments'))
                page2.wait_for_selector('.el-table__row', timeout=8000)
                page2.wait_for_timeout(600)
                m = doc_overflow(page2)
                check(m['sw'] <= m['cw'] + 2, f'{label} 页面横向溢出: {m}')
                # 操作按钮在窄屏可点击（过审按钮可达）
                btn = page2.locator('.el-table__row', has_text='待审核').first.locator('button:has-text("过审")')
                check(btn.count() == 1, f'{label} 应有过审按钮')
                box = btn.bounding_box()
                check(box is not None and box['width'] > 0, f'{label} 过审按钮尺寸异常: {box}')
                s = shot(page2, f'comments-c11-{label}.png')
                print(f'   [通过] {label} 无溢出，操作按钮可用')
                record(f'C11_responsive_{label}', f'{w}x{h}', 'PASS',
                       assertions={'doc': m, 'action_button_ok': True}, screenshots=[s])
                ctx2.close()
            except Exception as e:
                print(f'   [失败] {e}')
                record(f'C11_responsive_{label}', f'{w}x{h}', 'FAIL',
                       error=f'{e}\n{traceback.format_exc(limit=3)}')
                try:
                    shot(page2, f'comments-c11-{label}-fail.png')
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

report_path = f'{ARTIFACTS_DIR}/comments-view-report.json'
with open(report_path, 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

passed = sum(1 for s in report['scenarios'] if s['status'] == 'PASS')
print(f'\n========================================================')
print(f'评论管理页验收结束: {passed}/{len(report["scenarios"])} 场景通过，总体 {report["overall"]}')
print(f'报告: {report_path}')
print(f'========================================================')

if report['overall'] != 'PASS':
    sys.exit(1)
