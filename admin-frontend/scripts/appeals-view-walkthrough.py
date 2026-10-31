#!/usr/bin/env python3
"""
SchoolWall 管理后台 申诉管理页（AppealsView.vue）真实浏览器验收
（独立脚本；静态 dist + 单 Chromium 串行；Mock API + 全合成数据，非真实后端联调）

场景：
  AP1 初始加载（pending 参数契约）
  AP2 状态筛选（accepted/rejected）与空态
  AP3 分页
  AP4 列表接口失败与恢复
  AP5 接受申诉：说明长度校验（零请求）→ 有效输入 → POST 路径/请求体/列表刷新
  AP6 拒绝申诉：同样契约
  AP7 取消 prompt：静默（零 POST、无成功提示、无未处理 rejection）
  AP8 写请求失败：不误报成功、可重试、无未处理 rejection
  AP9 响应式 768/390（横向溢出与关键操作可用性）

产物：ci-artifacts/admin-ui/appeals-view-report.json + appeals-*.png
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

# ---------------------------------------------------------------- Mock 状态（全合成数据）
requests_log = []
page_errors = []      # 未处理异常/未处理 Promise rejection
console_errors = []
flags = {'list_error': False, 'list_empty': False, 'decision_error': False, 'decision_abort': False}

def make_appeal(i, status='pending'):
    return {
        'id': f'a-{i:04d}',
        'entity_type': ['post', 'comment', 'verification'][i % 3],
        'entity_id': f'{500 + i}',
        'reason': f'申诉理由 {i} 号：请复核该内容的完整语境',
        'status': status,
        'decision_reason': None if status == 'pending' else f'处理说明 {i}',
    }

APPEALS = [make_appeal(i) for i in range(1, 26)] + [make_appeal(101, 'accepted'), make_appeal(102, 'rejected')]

def appeals_page(query):
    st = query.get('status', 'pending')
    items = [a for a in APPEALS if a['status'] == st]
    total = len(items)
    page = int(query.get('page', 1))
    return items[(page - 1) * 20: page * 20], total

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
    if '/admin/appeals/' in path and req.method == 'POST' and path.rstrip('/').endswith('/decision'):
        requests_log.append({'method': 'POST', 'path': path, 'query': query, 'body': body})
        if flags['decision_abort']:
            return route.abort()
        if flags['decision_error']:
            return fulfill(route, {'detail': '处理失败，请重试'}, status=500)
        aid = path.rstrip('/').split('/')[-2]  # /admin/appeals/{id}/decision 的 id 在倒数第二段
        for a in APPEALS:
            if a['id'] == aid:
                a['status'] = (body or {}).get('decision', 'rejected')
                a['decision_reason'] = (body or {}).get('reason')
        return fulfill(route, {'code': 0, 'data': {'status': (body or {}).get('decision')}})
    if path.endswith('/admin/appeals'):
        requests_log.append({'method': 'GET', 'path': path, 'query': query, 'body': None})
        if flags['list_error']:
            return fulfill(route, {'detail': '申诉列表服务暂时不可用'}, status=500)
        if flags['list_empty']:
            return fulfill(route, {'code': 0, 'data': {'items': [], 'total': 0}})
        items, total = appeals_page(query)
        return fulfill(route, {'code': 0, 'data': {'items': items, 'total': total}})
    return fulfill(route, {'code': 0, 'message': 'ok', 'data': {'items': [], 'total': 0}})

# ---------------------------------------------------------------- 工具
class ScenarioFailure(Exception):
    pass

def check(cond, msg):
    if not cond:
        raise ScenarioFailure(msg)

report = {
    'task': 'admin AppealsView.vue browser acceptance (synthetic data only)',
    'date_utc': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
    'base_url': base_url,
    'browser': 'chromium(headless, single instance, serial)',
    'privacy': 'All records are programmatically synthesized; no real names, student IDs or credentials.',
    'mock_scope': 'All /api/v1/admin/** intercepted locally with contract fixtures; no real backend.',
    'unhandled_rejections': page_errors,
    'console_errors': console_errors,
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
    try:
        m = page.locator('.el-message')
        if m.count() == 0:
            return ''
        return m.last.inner_text(timeout=1500).strip()
    except Exception:
        # ElMessage 自动消散与读取竞态：元素在 count 与 inner_text 之间消失时视为无消息
        return ''

def new_errors_since(mark):
    return page_errors[mark:] + [e for e in console_errors[mark:]]

def new_admin_context(browser, width, height):
    ctx = browser.new_context(viewport={'width': width, 'height': height})
    ctx.add_cookies([
        {'name': 'sw_admin', 'value': 'mock-admin-token', 'domain': '127.0.0.1', 'path': '/'},
        {'name': 'sw_admin_csrf', 'value': 'mock-csrf-token', 'domain': '127.0.0.1', 'path': '/'},
    ])
    page = ctx.new_page()
    page.on('pageerror', lambda exc: page_errors.append(f'pageerror: {exc}'))
    def _on_console(m):
        # 浏览器对故意失败请求的原生资源日志不属 JS 缺陷；保留未处理 rejection 等真实信号
        if m.type == 'error' and not m.text.startswith('Failed to load resource'):
            console_errors.append(m.text)
    page.on('console', _on_console)
    page.route('**/api/v1/**', handle_admin_api)
    return ctx, page

def doc_overflow(page):
    return page.evaluate('''() => {
        const d = document.documentElement, b = document.body;
        return { sw: Math.max(d.scrollWidth, b.scrollWidth), cw: d.clientWidth };
    }''')

def pager_total(page):
    return page.locator('.el-pagination__total').inner_text().strip()

def select_status(page, label):
    page.locator('.el-select').first.click()
    page.wait_for_timeout(500)
    page.locator('.el-select-dropdown__item:visible', has_text=label).first.click()
    page.wait_for_timeout(400)
    page.keyboard.press('Escape')
    page.wait_for_timeout(400)

exit_code = 0
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx, page = new_admin_context(browser, 1280, 800)
        VP = '1280x800'

        # ================= AP1 初始加载 =================
        print('\n--- AP1 初始加载 ---')
        try:
            page.goto(route_url(base_url, '/appeals'))
            page.wait_for_selector('.el-table__row', timeout=8000)
            page.wait_for_timeout(600)
            check(page.locator('.el-table__row').count() == 20, '待处理首页应渲染 20 行')
            check('25' in pager_total(page), f'待处理总数应为 25，实际: {pager_total(page)}')
            q = last_requests('GET', '/admin/appeals')[0]['query']
            check(q.get('status') == 'pending' and q.get('page') == '1',
                  f'初始参数应为 status=pending&page=1，实际: {q}')
            s = shot(page, 'appeals-ap1-loaded.png')
            print('   [通过] 20 行 / 25 条 / 参数契约')
            record('AP1_initial_load', VP, 'PASS',
                   assertions={'rows': 20, 'total': 25, 'params': q}, screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('AP1_initial_load', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= AP2 状态筛选与空态 =================
        print('\n--- AP2 状态筛选与空态 ---')
        try:
            select_status(page, '已接受')
            q = last_requests('GET', '/admin/appeals')[0]['query']
            check(q.get('status') == 'accepted' and q.get('page') == '1',
                  f'已接受筛选参数: {q}')
            check(page.locator('.el-table__row').count() == 1, '已接受应有 1 行')
            check('处理说明 101' in page.locator('.el-table').inner_text(), '已接受应显示处理说明')

            select_status(page, '已拒绝')
            check(page.locator('.el-table__row').count() == 1, '已拒绝应有 1 行')

            # 空态：列表接口返回空（刷新触发）
            flags['list_empty'] = True
            page.locator('button:has-text("刷新")').click()
            page.wait_for_timeout(800)
            check(page.locator('.el-table__row').count() == 0, '空列表不应有数据行')
            check(page.locator('.el-table__empty-text').is_visible(), '空态提示应可见')
            flags['list_empty'] = False
            select_status(page, '待处理')
            check(page.locator('.el-table__row').count() == 20, '切回待处理应恢复 20 行')
            s = shot(page, 'appeals-ap2-filters.png')
            print('   [通过] accepted/rejected 参数、空态、恢复')
            record('AP2_status_filter_empty', VP, 'PASS',
                   assertions={'accepted_param': 'accepted', 'empty_state': True, 'recover': True},
                   screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('AP2_status_filter_empty', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= AP3 分页 =================
        print('\n--- AP3 分页 ---')
        try:
            page.locator('.el-pager li.number', has_text='2').first.click()
            page.wait_for_timeout(800)
            q = last_requests('GET', '/admin/appeals')[0]['query']
            check(q.get('page') == '2', f'翻页参数: {q}')
            check(page.locator('.el-table__row').count() == 5, '第 2 页应为 5 行')
            page.locator('.el-pager li.number', has_text='1').first.click()
            page.wait_for_timeout(800)
            print('   [通过] page=2 / 5 行')
            record('AP3_pagination', VP, 'PASS', assertions={'page2': '2', 'page2_rows': 5})
        except Exception as e:
            print(f'   [失败] {e}')
            record('AP3_pagination', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= AP4 列表失败与恢复 =================
        print('\n--- AP4 列表接口失败与恢复 ---')
        try:
            mark = len(page_errors) + len(console_errors)
            flags['list_error'] = True
            page.locator('button:has-text("刷新")').click()
            page.wait_for_timeout(800)
            check('申诉列表服务暂时不可用' in msg_text(page),
                  f'列表失败应有错误提示，实际: 「{msg_text(page)}」')
            flags['list_error'] = False
            page.locator('button:has-text("刷新")').click()
            page.wait_for_timeout(800)
            check(page.locator('.el-table__row').count() == 20,
                  f'恢复后应重新加载 20 行，实际 {page.locator(".el-table__row").count()}')
            print('   [通过] 失败提示/恢复重试')
            record('AP4_list_error_recover', VP, 'PASS',
                   assertions={'error_toast': True, 'recover': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('AP4_list_error_recover', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            flags['list_error'] = False

        # ================= AP5 接受申诉 =================
        print('\n--- AP5 接受申诉：校验/请求体/刷新 ---')
        try:
            row = page.locator('.el-table__row').first
            posts_before = count_requests('POST', '/decision')
            row.locator('button:has-text("接受")').click()
            page.wait_for_selector('.el-message-box', timeout=5000)
            # 短输入被 validator 拦截：零 POST、提示至少五个字
            page.locator('.el-message-box input').fill('短')
            page.locator('.el-message-box__btns button').last.click()
            page.wait_for_timeout(500)
            check('至少五个字' in page.locator('.el-message-box').inner_text(),
                  f'长度校验应提示，实际: {page.locator(".el-message-box").inner_text()[:120]}')
            check(count_requests('POST', '/decision') == posts_before, '校验失败不得发出 POST')

            page.locator('.el-message-box input').fill('复核完成，原内容语境无违规，接受申诉')
            page.locator('.el-message-box__btns button').last.click()
            page.wait_for_timeout(1200)
            check(count_requests('POST', '/decision') - posts_before == 1, '应恰好 1 次 POST')
            post = last_requests('POST', '/decision')[0]
            check('/admin/appeals/' in post['path'] and post['path'].rstrip('/').endswith('/decision'),
                  f'POST 路径应为 /admin/appeals/{{id}}/decision，实际: {post["path"]}')
            check(post['body'] == {'decision': 'accepted', 'reason': '复核完成，原内容语境无违规，接受申诉'},
                  f'接受请求体不符: {post["body"]}')
            page.wait_for_timeout(800)
            check('24' in pager_total(page),
                  f'已接受后待处理总数应为 24，实际: {pager_total(page)}')
            print('   [通过] 校验零请求、POST 路径/体正确、列表刷新')
            record('AP5_accept_flow', VP, 'PASS',
                   assertions={'validator_blocks': True, 'path': post['path'],
                               'body': post['body'], 'total_after': 24})
        except Exception as e:
            print(f'   [失败] {e}')
            record('AP5_accept_flow', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= AP6 拒绝申诉 =================
        print('\n--- AP6 拒绝申诉 ---')
        try:
            row = page.locator('.el-table__row').first
            aid = row.locator('td').nth(1).inner_text().strip()
            posts_before = count_requests('POST', '/decision')
            row.locator('button:has-text("拒绝")').click()
            page.wait_for_selector('.el-message-box', timeout=5000)
            page.locator('.el-message-box input').fill('证据不足，维持原审核结论')
            page.locator('.el-message-box__btns button').last.click()
            page.wait_for_timeout(1200)
            check(count_requests('POST', '/decision') - posts_before == 1, '应恰好 1 次 POST')
            post = last_requests('POST', '/decision')[0]
            check(post['body'] == {'decision': 'rejected', 'reason': '证据不足，维持原审核结论'},
                  f'拒绝请求体不符: {post["body"]}')
            print('   [通过] 拒绝请求体正确')
            record('AP6_reject_flow', VP, 'PASS',
                   assertions={'body': post['body']})
        except Exception as e:
            print(f'   [失败] {e}')
            record('AP6_reject_flow', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= AP7 取消 prompt：静默与未处理 rejection 检查 =================
        print('\n--- AP7 取消 prompt（静默 + 未处理 rejection 检查） ---')
        try:
            wait_mark = len(page_errors) + len(console_errors)
            posts_before = count_requests('POST', '/decision')
            row = page.locator('.el-table__row').first
            row.locator('button:has-text("接受")').click()
            page.wait_for_selector('.el-message-box', timeout=5000)
            page.locator('.el-message-box__btns button').first.click()  # 取消
            page.wait_for_timeout(1000)
            check(count_requests('POST', '/decision') == posts_before, '取消不得发出 POST')
            check('处理成功' not in msg_text(page) and '成功' not in msg_text(page),
                  f'取消不得显示成功提示，实际: 「{msg_text(page)}」')
            errs = new_errors_since(wait_mark)
            check(len(errs) == 0,
                  f'取消 prompt 不得产生未处理 Promise rejection / 页面错误，实际: {errs}')
            print('   [通过] 取消静默：零 POST、无成功提示、无未处理 rejection')
            record('AP7_cancel_prompt_silent', VP, 'PASS',
                   assertions={'no_post': True, 'no_success_toast': True, 'no_unhandled_rejection': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('AP7_cancel_prompt_silent', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= AP8 写请求失败：不误报成功 + 重试 =================
        print('\n--- AP8 写请求失败与重试（未处理 rejection 检查） ---')
        try:
            flags['decision_error'] = True
            wait_mark = len(page_errors) + len(console_errors)
            posts_before = count_requests('POST', '/decision')
            row = page.locator('.el-table__row').first
            row.locator('button:has-text("接受")').click()
            page.wait_for_selector('.el-message-box', timeout=5000)
            page.locator('.el-message-box input').fill('失败场景复核说明')
            page.locator('.el-message-box__btns button').last.click()
            page.wait_for_timeout(1000)
            check(count_requests('POST', '/decision') - posts_before == 1, '应发 1 次请求')
            check('处理失败，请重试' in msg_text(page), f'应展示错误提示，实际: 「{msg_text(page)}」')
            check('成功' not in msg_text(page), '失败不得误报成功')
            flags['decision_error'] = False

            # 网络中断
            flags['decision_abort'] = True
            row.locator('button:has-text("接受")').click()
            page.wait_for_selector('.el-message-box', timeout=5000)
            page.locator('.el-message-box input').fill('网络中断场景复核说明')
            page.locator('.el-message-box__btns button').last.click()
            page.wait_for_timeout(1000)
            check(count_requests('POST', '/decision') - posts_before == 2, 'abort 场景应发 1 次请求')
            check('成功' not in msg_text(page), '网络中断不得误报成功')
            flags['decision_abort'] = False

            # 重试成功
            row.locator('button:has-text("接受")').click()
            page.wait_for_selector('.el-message-box', timeout=5000)
            page.locator('.el-message-box input').fill('重试成功复核说明')
            page.locator('.el-message-box__btns button').last.click()
            page.wait_for_timeout(1200)
            check(count_requests('POST', '/decision') - posts_before == 3, '重试应发第 3 次请求')
            check('22' in pager_total(page),
                  f'重试成功后待处理总数应为 22，实际: {pager_total(page)}')

            errs = new_errors_since(wait_mark)
            check(len(errs) == 0,
                  f'写请求失败不得产生未处理 Promise rejection / 页面错误，实际: {errs}')
            s = shot(page, 'appeals-ap8-failure-retry.png')
            print('   [通过] 失败不误报、可重试成功、无未处理 rejection')
            record('AP8_decision_failure_retry', VP, 'PASS',
                   assertions={'error_toast': True, 'no_false_success': True,
                               'retry_success': True, 'no_unhandled_rejection': True,
                               'total_after': 22},
                   screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('AP8_decision_failure_retry', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            flags['decision_error'] = flags['decision_abort'] = False

        ctx.close()

        # ================= AP9 响应式 =================
        for label, w, h in [('tablet-768', 768, 1024), ('narrow-390', 390, 844)]:
            print(f'\n--- AP9 响应式 {label} ---')
            try:
                ctx2, page2 = new_admin_context(browser, w, h)
                page2.goto(route_url(base_url, '/appeals'))
                page2.wait_for_selector('.el-table__row', timeout=8000)
                page2.wait_for_timeout(600)
                m = doc_overflow(page2)
                check(m['sw'] <= m['cw'] + 2, f'{label} 页面横向溢出: {m}')
                btn = page2.locator('.el-table__row').first.locator('button:has-text("接受")')
                check(btn.count() == 1 and btn.is_visible(), f'{label} 接受按钮应可见')
                box = btn.bounding_box()
                check(box is not None and box['x'] >= 0 and box['x'] + box['width'] <= w + 1,
                      f'{label} 接受按钮超出视口: {box}')
                # prompt 弹窗在窄屏适配
                btn.click()
                page2.wait_for_selector('.el-message-box', timeout=5000)
                mb = page2.locator('.el-message-box').bounding_box()
                check(mb['x'] >= 0 and mb['x'] + mb['width'] <= w + 1,
                      f'{label} 处理弹窗超出视口: {mb} (视口 {w})')
                page2.locator('.el-message-box__btns button').first.click()
                page2.wait_for_timeout(400)
                m2 = doc_overflow(page2)
                s = shot(page2, f'appeals-ap9-{label}.png')
                print(f'   [通过] {label} 无溢出，操作按钮与弹窗适配')
                record(f'AP9_responsive_{label}', f'{w}x{h}', 'PASS',
                       assertions={'doc': m2, 'button_ok': True, 'prompt_dialog': mb},
                       screenshots=[s])
                ctx2.close()
            except Exception as e:
                print(f'   [失败] {e}')
                record(f'AP9_responsive_{label}', f'{w}x{h}', 'FAIL',
                       error=f'{e}\n{traceback.format_exc(limit=3)}')
                try:
                    shot(page2, f'appeals-ap9-{label}-fail.png')
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

report_path = f'{ARTIFACTS_DIR}/appeals-view-report.json'
with open(report_path, 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

passed = sum(1 for s in report['scenarios'] if s['status'] == 'PASS')
print(f'\n========================================================')
print(f'申诉管理页验收结束: {passed}/{len(report["scenarios"])} 场景通过，总体 {report["overall"]}')
print(f'未处理异常/错误: {len(page_errors) + len(console_errors)} 条')
print(f'报告: {report_path}')
print(f'========================================================')

if report['overall'] != 'PASS':
    sys.exit(1)
