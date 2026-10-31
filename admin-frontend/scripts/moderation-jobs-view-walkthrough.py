#!/usr/bin/env python3
"""
SchoolWall 管理后台 人工审核与故障队列页（ModerationJobsView.vue）真实浏览器验收
（独立脚本；静态 dist + 单 Chromium 串行；Mock API + 全合成数据，非真实后端联调）

场景：
  MJ1 初始加载（review 参数契约）
  MJ2 状态筛选（dead/pending/succeeded）与空态
  MJ3 分页与刷新
  MJ4 列表失败与恢复（含未处理 rejection 检查）
  MJ5 打开待审任务：正文/双图 Blob 显示/手写关闭释放（探针实测）
  MJ6 无图任务与切换任务：不残留旧图
  MJ7 媒体 403/404（过期）失败：不开窗、不残留、可恢复
  MJ8 理由校验：<2 字符零请求
  MJ9 通过：请求体/弹窗关闭/Blob 释放/列表刷新
  MJ10 拒绝：请求体契约
  MJ11 审核业务错误（409）：不误报成功、saving 释放、弹窗保持、重试成功
  MJ12 审核网络中断：不误报成功、可重试
  MJ13 机器重试：dead 可重试成功；非可重试状态 409 反馈；abort 不误报
  MJ14 响应式 768/390（760px 弹窗溢出检查）

产物：ci-artifacts/admin-ui/moderation-jobs-report.json + mj-*.png
任一断言失败 -> 场景 FAIL，退出码非零。
"""

import http.server
import json
import os
import socket
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

PNG_BYTES = bytes.fromhex(
    '89504e470d0a1a0a0000000d494844520000000100000001080600000'
    '01f15c4890000000d49444154789c626001000000ffff030000060005'
    '57bfabd40000000049454e44ae426082'
)

BLOB_SPY = '''
window.__blobLog = { created: [], revoked: [] };
(function () {
    const _c = URL.createObjectURL.bind(URL);
    const _r = URL.revokeObjectURL.bind(URL);
    URL.createObjectURL = function (b) { const u = _c(b); window.__blobLog.created.push(u); return u; };
    URL.revokeObjectURL = function (u) { window.__blobLog.revoked.push(u); return _r(u); };
})();
'''

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

httpd = http.server.ThreadingHTTPServer(('127.0.0.1', port), SPAHandler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
base_url = f'http://127.0.0.1:{port}'
print(f'Admin static server listening on {base_url}')

# ---------------------------------------------------------------- Mock 状态（全合成数据）
requests_log = []
page_errors = []
console_errors = []
flags = {'list_error': False, 'media_fail': None, 'review_error': False,
         'review_abort': False, 'retry_error': False, 'retry_abort': False}

def make_job(i, status='review'):
    # i%4==0：空正文（覆盖兜底文案路径）；i%2==1：带双图；i%2==0 且 i%4!=0：无图有文
    if i % 4 == 0:
        text = ''
    elif i % 2:
        text = f'待审文字 {i} 号：关于校园活动的内容'
    else:
        text = f'待审文字 {i} 号：无图纯文字内容'
    return {
        'id': f'job-{i:04d}', 'kind': 'moderate_post', 'status': status,
        'text': text,
        'media_ids': [f'm{i}a', f'm{i}b'] if i % 2 else [],
        'attempts': i % 4, 'last_error': 'worker timeout' if status == 'dead' else None,
    }

JOBS = ([make_job(i) for i in range(1, 26)] +
        [make_job(30, 'dead'), make_job(31, 'dead'), make_job(35, 'dead'),
         make_job(32, 'pending'), make_job(33, 'rejected')])
JOBS[-3]['attempts'] = 5

def jobs_page(query):
    st = query.get('status', 'review')
    items = [j for j in JOBS if j['status'] == st]
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
    if '/moderation-jobs/' in path and '/media/' in path:
        if flags['media_fail']:
            code = {'e403': 403, 'gone': 404}[flags['media_fail']]
            return fulfill(route, {'detail': 'forbidden/expired'}, status=code)
        return route.fulfill(status=200, content_type='image/png', body=PNG_BYTES)
    if '/moderation-jobs/' in path and path.rstrip('/').endswith('/retry'):
        requests_log.append({'method': 'POST', 'path': path, 'query': query, 'body': body})
        if flags['retry_abort']:
            return route.abort()
        if flags['retry_error']:
            # 模拟数据过期：任务已被其他管理员处理（契约 409）
            return fulfill(route, {'detail': '任务当前不可重试'}, status=409)
        jid = path.rstrip('/').split('/')[-2]
        job = next((j for j in JOBS if j['id'] == jid), None)
        if not job or job['status'] not in ('review', 'dead'):
            return fulfill(route, {'detail': '任务当前不可重试'}, status=409)
        job['status'] = 'pending'
        return fulfill(route, {'code': 0})
    if '/moderation-jobs/' in path and path.rstrip('/').endswith('/review'):
        requests_log.append({'method': 'POST', 'path': path, 'query': query, 'body': body})
        if flags['review_abort']:
            return route.abort()
        if flags['review_error']:
            return fulfill(route, {'detail': '任务当前不可审核，请刷新'}, status=409)
        jid = path.rstrip('/').split('/')[-2]
        job = next((j for j in JOBS if j['id'] == jid), None)
        if job:
            job['status'] = 'succeeded' if (body or {}).get('decision') == 'approve' else 'rejected'
        return fulfill(route, {'code': 0, 'data': {'status': (body or {}).get('decision')}})
    if path.endswith('/admin/moderation-jobs'):
        requests_log.append({'method': 'GET', 'path': path, 'query': query, 'body': None})
        if flags['list_error']:
            return fulfill(route, {'detail': '任务队列服务暂时不可用'}, status=500)
        items, total = jobs_page(query)
        return fulfill(route, {'code': 0, 'data': {'items': items, 'total': total}})
    return fulfill(route, {'code': 0, 'message': 'ok', 'data': {'items': [], 'total': 0}})

# ---------------------------------------------------------------- 工具
class ScenarioFailure(Exception):
    pass

def check(cond, msg):
    if not cond:
        raise ScenarioFailure(msg)

report = {
    'task': 'admin ModerationJobsView.vue browser acceptance (synthetic data only)',
    'date_utc': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
    'base_url': base_url,
    'browser': 'chromium(headless, single instance, serial)',
    'privacy': 'All records and images are programmatically synthesized; no real content or credentials.',
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
        return ''

def blob_log(page):
    return page.evaluate('() => window.__blobLog || { created: [], revoked: [] }')

def new_errors_since(mark):
    return page_errors[mark:] + [e for e in console_errors[mark:]]

def new_admin_context(browser, width, height):
    ctx = browser.new_context(viewport={'width': width, 'height': height})
    ctx.add_cookies([
        {'name': 'sw_admin', 'value': 'mock-admin-token', 'domain': '127.0.0.1', 'path': '/'},
        {'name': 'sw_admin_csrf', 'value': 'mock-csrf-token', 'domain': '127.0.0.1', 'path': '/'},
    ])
    ctx.add_init_script(BLOB_SPY)
    page = ctx.new_page()
    page.on('pageerror', lambda exc: page_errors.append(f'pageerror: {exc}'))
    def _on_console(m):
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

def wait_msgs_gone(page):
    page.wait_for_timeout(3200)

exit_code = 0
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx, page = new_admin_context(browser, 1280, 800)
        VP = '1280x800'

        # ================= MJ1 初始加载 =================
        print('\n--- MJ1 初始加载 ---')
        try:
            page.goto(f'{base_url}/moderation-jobs')
            page.wait_for_selector('.el-table__row', timeout=8000)
            page.wait_for_timeout(600)
            check(page.locator('.el-table__row').count() == 20, '待人工审核首页应渲染 20 行')
            check('25' in pager_total(page), f'待审核总数应为 25，实际: {pager_total(page)}')
            q = last_requests('GET', '/admin/moderation-jobs')[0]['query']
            check(q.get('status') == 'review' and q.get('page') == '1',
                  f'初始参数应为 status=review&page=1，实际: {q}')
            s = shot(page, 'mj-mj1-loaded.png')
            print('   [通过] 20 行 / 25 条 / 参数契约')
            record('MJ1_initial_load', VP, 'PASS',
                   assertions={'rows': 20, 'total': 25, 'params': q}, screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('MJ1_initial_load', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= MJ2 状态筛选与空态 =================
        print('\n--- MJ2 状态筛选与空态 ---')
        try:
            select_status(page, '重试耗尽')
            q = last_requests('GET', '/admin/moderation-jobs')[0]['query']
            check(q.get('status') == 'dead' and q.get('page') == '1', f'dead 筛选参数: {q}')
            check(page.locator('.el-table__row').count() == 3, '重试耗尽应有 3 行')
            check(page.locator('button:has-text("重试机器审核")').count() == 3, 'dead 行应有重试按钮')

            select_status(page, '已通过')
            check(page.locator('.el-table__row').count() == 0, '已通过应为空列表')
            check(page.locator('.el-table__empty-text').is_visible(), '空态提示应可见')
            select_status(page, '待人工审核')
            check(page.locator('.el-table__row').count() == 20, '切回待人工审核应恢复')
            s = shot(page, 'mj-mj2-filters.png')
            print('   [通过] dead 参数/重试按钮/空态/恢复')
            record('MJ2_status_filter_empty', VP, 'PASS',
                   assertions={'dead_param': 'dead', 'retry_buttons': 3, 'empty_state': True},
                   screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('MJ2_status_filter_empty', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= MJ3 分页与刷新 =================
        print('\n--- MJ3 分页与刷新 ---')
        try:
            page.locator('.el-pager li.number', has_text='2').first.click()
            page.wait_for_timeout(800)
            q = last_requests('GET', '/admin/moderation-jobs')[0]['query']
            check(q.get('page') == '2', f'翻页参数: {q}')
            check(page.locator('.el-table__row').count() == 5, '第 2 页应为 5 行')
            gets_before = count_requests('GET', '/admin/moderation-jobs')
            page.locator('button:has-text("刷新")').click()
            page.wait_for_timeout(800)
            check(count_requests('GET', '/admin/moderation-jobs') - gets_before == 1, '刷新应重新拉取')
            page.locator('.el-pager li.number', has_text='1').first.click()
            page.wait_for_timeout(800)
            print('   [通过] page=2 / 5 行 / 刷新生效')
            record('MJ3_pagination_refresh', VP, 'PASS',
                   assertions={'page2': '2', 'page2_rows': 5, 'refresh': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('MJ3_pagination_refresh', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= MJ4 列表失败与恢复（未处理 rejection 检查） =================
        print('\n--- MJ4 列表失败与恢复 ---')
        try:
            mark = len(page_errors) + len(console_errors)
            flags['list_error'] = True
            page.locator('button:has-text("刷新")').click()
            page.wait_for_timeout(800)
            check('任务队列服务暂时不可用' in msg_text(page),
                  f'列表失败应有错误提示，实际: 「{msg_text(page)}」')
            check(page.locator('.el-loading-mask').count() == 0, '失败后 loading 应释放')
            flags['list_error'] = False
            page.locator('button:has-text("刷新")').click()
            page.wait_for_timeout(800)
            check(page.locator('.el-table__row').count() == 20, '恢复后应重新加载')
            errs = new_errors_since(mark)
            check(len(errs) == 0, f'列表失败不得产生未处理 rejection，实际: {errs}')
            print('   [通过] 失败提示/loading 释放/恢复/无未处理 rejection')
            record('MJ4_list_error_recover', VP, 'PASS',
                   assertions={'error_toast': True, 'loading_released': True,
                               'no_unhandled_rejection': True, 'recover': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('MJ4_list_error_recover', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            flags['list_error'] = False

        # ================= MJ5 打开任务与 Blob 释放 =================
        print('\n--- MJ5 打开任务：正文/图片/Blob 释放 ---')
        try:
            page.evaluate('() => { window.__blobLog = { created: [], revoked: [] } }')
            page.locator('.el-table__row').first.locator('button:has-text("查看 / 决定")').click()
            page.wait_for_selector('.el-dialog:visible', timeout=5000)
            page.wait_for_timeout(800)
            dlg = page.locator('.el-dialog:visible')
            check('待审文字 1 号' in dlg.inner_text(), '正文应显示')
            check(dlg.locator('img.preview').count() == 2, '应显示 2 张待审图片')
            log = blob_log(page)
            check(len(log['created']) == 2, f'应创建 2 个 Blob URL，实际: {log}')
            s = shot(page, 'mj-mj5-opened.png')
            dlg.locator('button:has-text("关闭")').click()
            page.wait_for_timeout(600)
            log = blob_log(page)
            check(all(u in log['revoked'] for u in log['created']),
                  f'关闭后 Blob URL 应全部释放，探针: {log}')
            print('   [通过] 正文/2 图 Blob 显示/关闭全释放')
            record('MJ5_open_and_blob_cleanup', VP, 'PASS',
                   assertions={'text': True, 'images': 2, 'blob_created': 2, 'all_revoked': True},
                   screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('MJ5_open_and_blob_cleanup', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= MJ6 无图任务与切换 =================
        print('\n--- MJ6 无图任务与切换不残留 ---')
        try:
            page.evaluate('() => { window.__blobLog = { created: [], revoked: [] } }')
            # 行 4（i=4）空正文且无图
            page.locator('.el-table__row').nth(3).locator('button:has-text("查看 / 决定")').click()
            page.wait_for_selector('.el-dialog:visible', timeout=5000)
            page.wait_for_timeout(500)
            dlg = page.locator('.el-dialog:visible')
            check('请核对图片内容' in dlg.inner_text(), '空正文任务应显示兜底文案')
            check(dlg.locator('img.preview').count() == 0, '无图任务不应渲染图片')
            log = blob_log(page)
            check(len(log['created']) == 0, f'无图任务不得创建 Blob URL，探针: {log}')

            # 切换到有图任务：旧图不残留
            page.locator('.el-dialog:visible button:has-text("关闭")').click()
            page.wait_for_timeout(500)
            page.locator('.el-table__row').first.locator('button:has-text("查看 / 决定")').click()
            page.wait_for_selector('.el-dialog:visible', timeout=5000)
            page.wait_for_timeout(800)
            check(page.locator('.el-dialog:visible img.preview').count() == 2,
                  '切换后应显示新任务的 2 张图，不得残留旧图')
            page.locator('.el-dialog:visible button:has-text("关闭")').click()
            page.wait_for_timeout(600)
            log = blob_log(page)
            check(all(u in log['revoked'] for u in log['created']),
                  f'切换/关闭后 Blob 应全部释放，探针: {log}')
            print('   [通过] 无图兜底/切换不残留/释放正确')
            record('MJ6_no_image_and_switch', VP, 'PASS',
                   assertions={'fallback_text': True, 'no_blobs': True, 'switch_clean': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('MJ6_no_image_and_switch', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            try:
                if page.locator('.el-dialog:visible').count():
                    page.locator('.el-dialog:visible button:has-text("关闭")').click()
                    page.wait_for_timeout(400)
            except Exception:
                pass

        # ================= MJ7 媒体失败路径 =================
        print('\n--- MJ7 媒体 403/404 失败路径 ---')
        try:
            for mode, expect in [('e403', 'forbidden/expired'), ('gone', 'forbidden/expired')]:
                wait_msgs_gone(page)
                flags['media_fail'] = mode
                page.locator('.el-table__row').first.locator('button:has-text("查看 / 决定")').click()
                page.wait_for_timeout(1000)
                check(page.locator('.el-dialog:visible').count() == 0,
                      f'{mode} 失败不得打开弹窗（避免显示不完整内容）')
                check(page.locator('.el-message--error').count() >= 1,
                      f'{mode} 失败应有错误提示')
                check(page.evaluate('() => window.__blobLog.created.length') ==
                      page.evaluate('() => window.__blobLog.revoked.length'),
                      f'{mode} 失败不得残留已创建的 Blob URL')
            flags['media_fail'] = None
            page.locator('.el-table__row').first.locator('button:has-text("查看 / 决定")').click()
            page.wait_for_selector('.el-dialog:visible', timeout=5000)
            page.locator('.el-dialog:visible button:has-text("关闭")').click()
            page.wait_for_timeout(500)
            print('   [通过] 403/404 不开窗、不残留、可恢复（401 由全局拦截器统一处理，已在学生证页验证同类行为）')
            record('MJ7_media_failure_paths', VP, 'PASS',
                   assertions={'e403_no_dialog': True, 'gone_no_dialog': True,
                               'no_blob_leak': True, 'recoverable': True,
                               'note': '401 走全局拦截器跳登录，与学生证页同类行为'})
        except Exception as e:
            print(f'   [失败] {e}')
            record('MJ7_media_failure_paths', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            flags['media_fail'] = None
            try:
                if page.locator('.el-dialog:visible').count():
                    page.locator('.el-dialog:visible button:has-text("关闭")').click()
                    page.wait_for_timeout(400)
            except Exception:
                pass

        # ================= MJ8 理由校验 =================
        print('\n--- MJ8 理由校验（<2 字符零请求） ---')
        try:
            wait_msgs_gone(page)
            posts_before = count_requests('POST', '/review')
            page.locator('.el-table__row').first.locator('button:has-text("查看 / 决定")').click()
            page.wait_for_selector('.el-dialog:visible', timeout=5000)
            page.locator('.el-dialog:visible textarea').fill('短')
            page.locator('.el-dialog:visible button:has-text("确认全部通过")').click()
            page.wait_for_timeout(600)
            check(count_requests('POST', '/review') == posts_before, '理由不足不得发出请求')
            check('请填写至少两个字的理由' in msg_text(page),
                  f'应有校验提示，实际: 「{msg_text(page)}」')
            print('   [通过] 理由不足零请求并有提示')
            record('MJ8_reason_validation', VP, 'PASS',
                   assertions={'no_request': True, 'warning': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('MJ8_reason_validation', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= MJ9 通过 =================
        print('\n--- MJ9 通过审核 ---')
        try:
            wait_msgs_gone(page)
            page.evaluate('() => { window.__blobLog = { created: [], revoked: [] } }')
            row_text_before = page.locator('.el-table__row').first.locator('td').nth(1).inner_text().strip()
            posts_before = count_requests('POST', '/review')
            page.locator('.el-dialog:visible textarea').fill('图文核对一致，通过')
            page.locator('.el-dialog:visible button:has-text("确认全部通过")').click()
            page.wait_for_timeout(1200)
            check(count_requests('POST', '/review') - posts_before == 1, '应恰好 1 次审核 POST')
            post = last_requests('POST', '/review')[0]
            check('/moderation-jobs/' in post['path'] and post['path'].rstrip('/').endswith('/review'),
                  f'POST 路径应为 /moderation-jobs/{{id}}/review，实际: {post["path"]}')
            check(post['body'] == {'decision': 'approve', 'reason': '图文核对一致，通过'},
                  f'通过请求体不符: {post["body"]}')
            check(page.locator('.el-dialog:visible').count() == 0, '成功后弹窗应关闭')
            log = blob_log(page)
            if log['created']:
                check(all(u in log['revoked'] for u in log['created']),
                      f'成功后 Blob 应释放，探针: {log}')
            page.wait_for_timeout(800)
            check(row_text_before not in page.locator('.el-table').inner_text(),
                  f'已通过任务应从待审核视图移除（{row_text_before}）')
            s = shot(page, 'mj-mj9-approve.png')
            print('   [通过] 1 次 POST、请求体正确、关窗释放、列表刷新')
            record('MJ9_approve', VP, 'PASS',
                   assertions={'body': post['body'], 'dialog_closed': True,
                               'blobs_revoked': True, 'row_removed': True}, screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('MJ9_approve', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= MJ10 拒绝 =================
        print('\n--- MJ10 拒绝审核 ---')
        try:
            wait_msgs_gone(page)
            page.locator('.el-table__row').first.locator('button:has-text("查看 / 决定")').click()
            page.wait_for_selector('.el-dialog:visible', timeout=5000)
            page.locator('.el-dialog:visible textarea').fill('图片与描述不符，拒绝')
            page.locator('.el-dialog:visible button:has-text("拒绝")').click()
            page.wait_for_timeout(1200)
            post = last_requests('POST', '/review')[0]
            check(post['body'] == {'decision': 'reject', 'reason': '图片与描述不符，拒绝'},
                  f'拒绝请求体不符: {post["body"]}')
            print('   [通过] 拒绝请求体正确')
            record('MJ10_reject', VP, 'PASS', assertions={'body': post['body']})
        except Exception as e:
            print(f'   [失败] {e}')
            record('MJ10_reject', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= MJ11 审核业务错误与重试 =================
        print('\n--- MJ11 审核业务错误（409）与重试 ---')
        try:
            wait_msgs_gone(page)
            flags['review_error'] = True
            page.locator('.el-table__row').first.locator('button:has-text("查看 / 决定")').click()
            page.wait_for_selector('.el-dialog:visible', timeout=5000)
            page.locator('.el-dialog:visible textarea').fill('业务错误场景理由')
            page.locator('.el-dialog:visible button:has-text("确认全部通过")').click()
            page.wait_for_timeout(1000)
            check('任务当前不可审核，请刷新' in msg_text(page),
                  f'业务错误应展示，实际: 「{msg_text(page)}」')
            btn_class = page.locator('.el-dialog:visible button:has-text("确认全部通过")').get_attribute('class') or ''
            check('is-loading' not in btn_class, '失败后 saving 应释放')
            check(page.locator('.el-dialog:visible').count() >= 1, '失败后弹窗应保持打开')
            flags['review_error'] = False
            page.locator('.el-dialog:visible button:has-text("确认全部通过")').click()
            page.wait_for_timeout(1200)
            check(page.locator('.el-dialog:visible').count() == 0, '重试应成功关闭弹窗')
            s = shot(page, 'mj-mj11-error-retry.png')
            print('   [通过] 业务错误展示、saving 释放、弹窗保持、重试成功')
            record('MJ11_review_error_retry', VP, 'PASS',
                   assertions={'error_toast': True, 'saving_released': True, 'retry_ok': True},
                   screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('MJ11_review_error_retry', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            flags['review_error'] = False

        # ================= MJ12 审核网络中断 =================
        print('\n--- MJ12 审核网络中断与重试 ---')
        try:
            wait_msgs_gone(page)
            flags['review_abort'] = True
            posts_before = count_requests('POST', '/review')
            page.locator('.el-table__row').first.locator('button:has-text("查看 / 决定")').click()
            page.wait_for_selector('.el-dialog:visible', timeout=5000)
            page.locator('.el-dialog:visible textarea').fill('网络中断场景理由')
            page.locator('.el-dialog:visible button:has-text("确认全部通过")').click()
            page.wait_for_timeout(1000)
            check(count_requests('POST', '/review') - posts_before == 1, 'abort 场景应发 1 次请求')
            check(page.locator('.el-dialog:visible').count() >= 1, '网络失败后弹窗应保持')
            btn_class = page.locator('.el-dialog:visible button:has-text("确认全部通过")').get_attribute('class') or ''
            check('is-loading' not in btn_class, '网络失败后 saving 应释放')
            flags['review_abort'] = False
            page.locator('.el-dialog:visible button:has-text("确认全部通过")').click()
            page.wait_for_timeout(1200)
            check(page.locator('.el-dialog:visible').count() == 0, '恢复后重试应成功')
            print('   [通过] 网络中断不误报成功、saving 释放、重试成功')
            record('MJ12_review_network_retry', VP, 'PASS',
                   assertions={'abort_requests': 1, 'no_false_success': True, 'retry_ok': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('MJ12_review_network_retry', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            flags['review_abort'] = False
            try:
                if page.locator('.el-dialog:visible').count():
                    page.locator('.el-dialog:visible button:has-text("关闭")').click()
                    page.wait_for_timeout(400)
            except Exception:
                pass

        # ================= MJ13 机器重试 =================
        print('\n--- MJ13 机器重试：成功/业务错误/中断 ---')
        try:
            select_status(page, '重试耗尽')
            retries_before = count_requests('POST', '/retry')
            page.locator('.el-table__row').first.locator('button:has-text("重试机器审核")').click()
            page.wait_for_timeout(1000)
            check(count_requests('POST', '/retry') - retries_before == 1, '重试应发 1 次 POST')
            check('已进入重试队列' in msg_text(page), f'应有成功提示，实际: 「{msg_text(page)}」')
            check(page.locator('.el-table__row').count() == 2, '重试后任务应从 dead 列表移除')

            # 业务错误：对 review 状态重试 → mock 返回 409
            select_status(page, '待人工审核')
            flags['retry_error'] = True
            errs_mark = len(page_errors) + len(console_errors)
            page.locator('.el-table__row').first.locator('button:has-text("重试机器审核")').click()
            page.wait_for_timeout(1000)
            check('任务当前不可重试' in msg_text(page),
                  f'业务错误应展示，实际: 「{msg_text(page)}」')
            check('已进入重试队列' not in msg_text(page), '业务错误不得误报成功')
            flags['retry_error'] = False

            # 网络中断：不误报
            flags['retry_abort'] = True
            page.locator('.el-table__row').first.locator('button:has-text("重试机器审核")').click()
            page.wait_for_timeout(1000)
            check('已进入重试队列' not in msg_text(page), '网络中断不得误报成功')
            flags['retry_abort'] = False
            select_status(page, '待人工审核')
            errs = new_errors_since(errs_mark)
            check(len(errs) == 0, f'重试失败不得产生未处理 rejection，实际: {errs}')
            print('   [通过] 成功提示/409 反馈/中断不误报/无未处理 rejection')
            record('MJ13_machine_retry', VP, 'PASS',
                   assertions={'success_toast': True, 'biz_error': True,
                               'abort_no_false_success': True, 'no_unhandled_rejection': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('MJ13_machine_retry', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            flags['retry_error'] = flags['retry_abort'] = False

        ctx.close()

        # ================= MJ14 响应式 =================
        for label, w, h in [('tablet-768', 768, 1024), ('narrow-390', 390, 844)]:
            print(f'\n--- MJ14 响应式 {label} ---')
            try:
                ctx2, page2 = new_admin_context(browser, w, h)
                page2.goto(f'{base_url}/moderation-jobs')
                page2.wait_for_selector('.el-table__row', timeout=8000)
                page2.wait_for_timeout(600)
                m = doc_overflow(page2)
                check(m['sw'] <= m['cw'] + 2, f'{label} 页面横向溢出: {m}')
                page2.locator('button:has-text("查看 / 决定")').first.click()
                page2.wait_for_selector('.el-dialog:visible', timeout=5000)
                page2.wait_for_timeout(800)
                dlg = page2.locator('.el-dialog:visible').first.bounding_box()
                check(dlg['x'] >= 0 and dlg['x'] + dlg['width'] <= w + 1,
                      f'{label} 760px 审核弹窗超出视口: {dlg} (视口 {w})')
                for btn_text in ['拒绝', '确认全部通过']:
                    btn = page2.locator(f'.el-dialog:visible button:has-text("{btn_text}")')
                    check(btn.count() >= 1 and btn.first.is_visible(), f'{label} 按钮「{btn_text}」应可用')
                m2 = doc_overflow(page2)
                check(m2['sw'] <= m2['cw'] + 2, f'{label} 弹窗打开后页面横向溢出: {m2}')
                s = shot(page2, f'mj-mj14-{label}.png')
                print(f'   [通过] {label} 无溢出，弹窗与按钮适配')
                record(f'MJ14_responsive_{label}', f'{w}x{h}', 'PASS',
                       assertions={'doc': m2, 'dialog': dlg, 'buttons_ok': True}, screenshots=[s])
                ctx2.close()
            except Exception as e:
                print(f'   [失败] {e}')
                record(f'MJ14_responsive_{label}', f'{w}x{h}', 'FAIL',
                       error=f'{e}\n{traceback.format_exc(limit=3)}')
                try:
                    shot(page2, f'mj-mj14-{label}-fail.png')
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

report_path = f'{ARTIFACTS_DIR}/moderation-jobs-report.json'
with open(report_path, 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

passed = sum(1 for s in report['scenarios'] if s['status'] == 'PASS')
print(f'\n========================================================')
print(f'人工审核队列页验收结束: {passed}/{len(report["scenarios"])} 场景通过，总体 {report["overall"]}')
print(f'未处理异常/错误: {len(page_errors) + len(console_errors)} 条')
print(f'报告: {report_path}')
print(f'========================================================')

if report['overall'] != 'PASS':
    sys.exit(1)
