#!/usr/bin/env python3
"""
SchoolWall 管理后台 学生证人工认证页（StudentVerificationsView.vue）真实浏览器验收
（独立脚本；静态 dist + 单 Chromium 串行；Mock API + 全合成数据，非真实后端联调）

隐私声明：所有数据与图片均为程序合成，不含任何真实姓名、学号、证件或凭据。

场景：
  V1 初始加载（pending 参数契约）
  V2 状态筛选与空态
  V3 分页与刷新
  V4 列表加载失败与恢复
  V5 证件 Blob 读取成功 + evidence_available=false 无入口
  V6 证件 401/403/过期 三类失败路径与重试
  V7 Blob URL 释放（关弹窗/换条/审核后均 revoke，探针实测）
  V8 通过审核：核对项不全零请求 → 补齐后请求体正确
  V9 拒绝审核：理由必填零请求 → 填写后请求体正确
  V10 审核业务错误/网络失败后 saving 释放与重试
  V11 撤销认证：理由校验/取消零 POST/成功刷新
  V12 响应式 768/390（760px 弹窗溢出检查）

产物：ci-artifacts/admin-ui/student-verifications-report.json + sv-*.png
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
httpd, base_url = create_server(DIST_DIR)
print(f'Admin static server listening on {base_url}')

# ---------------------------------------------------------------- Mock 状态（全合成数据）
requests_log = []
flags = {'list_error': False, 'evidence_mode': 'ok', 'review_error': False,
         'review_abort': False, 'revoke_abort': False}

def make_item(i, status='pending'):
    return {
        'id': f'sv-{i:04d}', 'user_id': f'u{i:03d}', 'nickname': f'合成用户{i}号',
        'school_id': '鄂尔多斯应用技术学院', 'status': status,
        'challenge_code': f'CODE{i:04d}', 'card_valid_until': '2027-06-30',
        'evidence_available': i % 4 != 0,   # 每 4 个一条无证件
        'created_at': f'2026-10-{min(i, 28):02d}T08:00:00Z',
        'submitted_at': f'2026-10-{min(i, 28):02d}T09:00:00Z',
    }

ITEMS = [make_item(i) for i in range(1, 26)] + [make_item(30, 'approved')]

def items_page(query):
    st = query.get('status', 'pending')
    items = [r for r in ITEMS if r['status'] == st]
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
    if '/student-verifications/' in path and path.rstrip('/').endswith('/evidence'):
        requests_log.append({'method': 'GET', 'path': path, 'query': query, 'body': None})
        mode = flags['evidence_mode']
        if mode == 'e401':
            return fulfill(route, {'detail': 'unauthorized'}, status=401)
        if mode == 'e403':
            return fulfill(route, {'detail': 'forbidden'}, status=403)
        if mode == 'gone':
            return fulfill(route, {'detail': 'not found'}, status=404)
        return route.fulfill(status=200, content_type='image/png', body=PNG_BYTES)
    if '/student-verifications/' in path and req.method == 'POST' and path.rstrip('/').endswith('/review'):
        if flags['review_abort']:
            return route.abort()
        requests_log.append({'method': 'POST', 'path': path, 'query': query, 'body': body})
        if flags['review_error']:
            return fulfill(route, {'detail': '该记录已被其他管理员处理'}, status=409)
        rid = path.rstrip('/').split('/')[-2]
        for r in ITEMS:
            if r['id'] == rid:
                r['status'] = (body or {}).get('decision', 'rejected')
        return fulfill(route, {'code': 0, 'data': {'status': (body or {}).get('decision')}})
    if '/student-verifications/' in path and req.method == 'POST' and path.rstrip('/').endswith('/revoke'):
        if flags['revoke_abort']:
            return route.abort()
        requests_log.append({'method': 'POST', 'path': path, 'query': query, 'body': body})
        rid = path.rstrip('/').split('/')[-2]
        for r in ITEMS:
            if r['id'] == rid:
                r['status'] = 'revoked'
        return fulfill(route, {'code': 0, 'data': {'status': 'revoked'}})
    if path.endswith('/admin/student-verifications'):
        requests_log.append({'method': 'GET', 'path': path, 'query': query, 'body': None})
        if flags['list_error']:
            return fulfill(route, {'detail': '认证列表服务暂时不可用'}, status=500)
        items, total = items_page(query)
        return fulfill(route, {'code': 0, 'data': {'items': items, 'total': total}})
    return fulfill(route, {'code': 0, 'message': 'ok', 'data': {'items': [], 'total': 0}})

# ---------------------------------------------------------------- 工具
class ScenarioFailure(Exception):
    pass

def check(cond, msg):
    if not cond:
        raise ScenarioFailure(msg)

report = {
    'task': 'admin StudentVerificationsView.vue browser acceptance (synthetic data only)',
    'date_utc': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
    'base_url': base_url,
    'browser': 'chromium(headless, single instance, serial)',
    'privacy': 'All records and images are programmatically synthesized; no real names, student IDs, cards or credentials.',
    'mock_scope': 'All /api/v1/admin/** intercepted locally with contract fixtures; no real backend.',
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

def blob_log(page):
    return page.evaluate('() => window.__blobLog || { created: [], revoked: [] }')

def new_admin_context(browser, width, height):
    ctx = browser.new_context(viewport={'width': width, 'height': height})
    ctx.add_cookies([
        {'name': 'sw_admin', 'value': 'mock-admin-token', 'domain': '127.0.0.1', 'path': '/'},
        {'name': 'sw_admin_csrf', 'value': 'mock-csrf-token', 'domain': '127.0.0.1', 'path': '/'},
    ])
    ctx.add_init_script(BLOB_SPY)
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

def select_status(page, label):
    page.locator('.el-form-item', has_text='状态').locator('.el-select').first.click()
    page.wait_for_timeout(500)
    page.locator('.el-select-dropdown__item:visible', has_text=label).first.click()
    page.wait_for_timeout(800)

exit_code = 0
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx, page = new_admin_context(browser, 1280, 800)
        VP = '1280x800'

        # ================= V1 初始加载 =================
        print('\n--- V1 初始加载 ---')
        try:
            page.goto(route_url(base_url, '/student-verifications'))
            page.wait_for_selector('.el-table__row', timeout=8000)
            page.wait_for_timeout(600)
            check(page.locator('.el-table__row').count() == 20, '待审核首页应渲染 20 行')
            check('25' in pager_total(page), f'待审核总数应为 25，实际: {pager_total(page)}')
            q = last_requests('GET', '/admin/student-verifications')[0]['query']
            check(q.get('status') == 'pending' and q.get('page') == '1',
                  f'初始参数应为 status=pending&page=1，实际: {q}')
            s = shot(page, 'sv-v1-loaded.png')
            print('   [通过] 20 行 / 25 条 / 参数契约')
            record('V1_initial_load', VP, 'PASS',
                   assertions={'rows': 20, 'total': 25, 'params': q}, screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('V1_initial_load', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= V2 状态筛选与空态 =================
        print('\n--- V2 状态筛选与空态 ---')
        try:
            select_status(page, '已通过')
            q = last_requests('GET', '/admin/student-verifications')[0]['query']
            check(q.get('status') == 'approved', f'已通过筛选参数: {q}')
            check(page.locator('.el-table__row').count() == 1, '已通过应有 1 行')
            check(page.locator('button:has-text("撤销认证")').count() == 1, '已通过行应有撤销按钮')

            select_status(page, '已拒绝')
            check(page.locator('.el-table__row').count() == 0, '已拒绝应为空列表')
            check(page.locator('.el-table__empty-text').is_visible(), '空态提示应可见')
            select_status(page, '待审核')
            check(page.locator('.el-table__row').count() == 20, '切回待审核应恢复')
            s = shot(page, 'sv-v2-filters.png')
            print('   [通过] approved 参数/撤销入口/空态/恢复')
            record('V2_status_filter_empty', VP, 'PASS',
                   assertions={'approved_param': 'approved', 'revoke_button': True,
                               'empty_state': True}, screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('V2_status_filter_empty', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= V3 分页与刷新 =================
        print('\n--- V3 分页与刷新 ---')
        try:
            page.locator('.el-pager li.number', has_text='2').first.click()
            page.wait_for_timeout(800)
            q = last_requests('GET', '/admin/student-verifications')[0]['query']
            check(q.get('page') == '2', f'翻页参数: {q}')
            check(page.locator('.el-table__row').count() == 5, '第 2 页应为 5 行')
            gets_before = count_requests('GET', '/admin/student-verifications')
            page.locator('button:has-text("刷新")').click()
            page.wait_for_timeout(800)
            check(count_requests('GET', '/admin/student-verifications') - gets_before == 1,
                  '刷新应重新拉取列表')
            page.locator('.el-pager li.number', has_text='1').first.click()
            page.wait_for_timeout(800)
            print('   [通过] page=2 / 5 行 / 刷新生效')
            record('V3_pagination_refresh', VP, 'PASS',
                   assertions={'page2': '2', 'page2_rows': 5, 'refresh_reload': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('V3_pagination_refresh', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= V4 列表失败与恢复 =================
        print('\n--- V4 列表加载失败与恢复 ---')
        try:
            wait_msgs_gone(page)
            flags['list_error'] = True
            page.locator('button:has-text("刷新")').click()
            page.wait_for_timeout(800)
            check('认证列表服务暂时不可用' in msg_text(page),
                  f'列表失败应有错误提示，实际: 「{msg_text(page)}」')
            check(page.locator('.el-loading-mask').count() == 0, '失败后 loading 应释放')
            flags['list_error'] = False
            page.locator('button:has-text("刷新")').click()
            page.wait_for_timeout(800)
            check(page.locator('.el-table__row').count() == 20, '恢复后应重新加载')
            print('   [通过] 失败提示/loading 释放/恢复重试')
            record('V4_list_error_recover', VP, 'PASS',
                   assertions={'error_toast': True, 'loading_released': True, 'recover': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('V4_list_error_recover', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            flags['list_error'] = False

        # ================= V5 证件读取成功 + 无证件无入口 =================
        print('\n--- V5 证件 Blob 读取 ---')
        try:
            ev_before = count_requests('GET', '/evidence')
            page.locator('.el-table__row').first.locator('button:has-text("查看证件 / 审核")').click()
            page.wait_for_selector('.el-dialog:visible', timeout=5000)
            page.wait_for_timeout(600)
            check(count_requests('GET', '/evidence') - ev_before == 1, '应发起 1 次证件请求')
            img = page.locator('.el-dialog:visible img.proof')
            check(img.count() == 1 and (img.get_attribute('src') or '').startswith('blob:'),
                  '证件图应以 Blob URL 显示')
            check('CODE0001' in page.locator('.el-dialog:visible').inner_text(), '应显示同框手写码')
            log = blob_log(page)
            check(len(log['created']) >= 1, 'Blob 探针应记录 createObjectURL')
            s = shot(page, 'sv-v5-evidence.png')

            # 无证件行（i=4 → evidence_available=false）
            page.locator('.el-dialog:visible button:has-text("关闭")').click()
            page.wait_for_timeout(600)
            row4 = page.locator('.el-table__row', has_text='合成用户4号')
            check(row4.locator('button:has-text("查看证件 / 审核")').count() == 0,
                  'evidence_available=false 的记录不应有查看入口')
            print('   [通过] Blob 显示/手写码/无证件无入口')
            record('V5_evidence_blob', VP, 'PASS',
                   assertions={'evidence_requests': 1, 'blob_img': True,
                               'challenge_code': True, 'no_entry_without_evidence': True},
                   screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('V5_evidence_blob', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= V6 证件失败路径 =================
        print('\n--- V6 证件 401/403/过期失败路径 ---')
        try:
            # 403/过期：拦截器提示 + evidenceBlob 映射提示（最后一条为映射文案）
            for mode, expect in [('e403', '需要有效管理员权限与多因素认证'),
                                 ('gone', '无法读取照片或已过保留期')]:
                wait_msgs_gone(page)
                flags['evidence_mode'] = mode
                page.locator('.el-table__row').first.locator('button:has-text("查看证件 / 审核")').click()
                page.wait_for_timeout(800)
                check(expect in msg_text(page),
                      f'{mode} 应提示「{expect}」，实际: 「{msg_text(page)}」')
                check(page.locator('.el-dialog:visible').count() == 0, f'{mode} 失败不得打开弹窗')
            flags['evidence_mode'] = 'ok'
            page.locator('.el-table__row').first.locator('button:has-text("查看证件 / 审核")').click()
            page.wait_for_selector('.el-dialog:visible', timeout=5000)
            page.locator('.el-dialog:visible button:has-text("关闭")').click()
            page.wait_for_timeout(500)

            # 401：全局拦截器清会话并跳登录（登录页会清理会话 Cookie，需全新上下文验证，
            # 避免污染后续场景——这是既定安全行为，非 evidenceBlob 映射路径）
            ctx401, page401 = new_admin_context(browser, 1280, 800)
            page401.goto(route_url(base_url, '/student-verifications'))
            page401.wait_for_selector('.el-table__row', timeout=8000)
            flags['evidence_mode'] = 'e401'
            page401.locator('.el-table__row').first.locator('button:has-text("查看证件 / 审核")').click()
            page401.wait_for_timeout(1500)
            check('/login' in page401.url,
                  f'401 应由全局拦截器跳转登录页，实际 URL: {page401.url}')
            check(page401.locator('.el-dialog:visible').count() == 0, '401 不得停留在审核弹窗')
            ctx401.close()
            flags['evidence_mode'] = 'ok'
            print('   [通过] 401 全局跳登录（独立上下文）、403/过期映射提示正确，失败不开窗，重试成功')
            record('V6_evidence_error_paths', VP, 'PASS',
                   assertions={'e401_redirects_login': True, 'e403': True, 'gone': True, 'retry_ok': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('V6_evidence_error_paths', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            flags['evidence_mode'] = 'ok'

        # ================= V7 Blob URL 释放 =================
        print('\n--- V7 Blob URL 释放（探针实测） ---')
        try:
            page.evaluate('() => { window.__blobLog = { created: [], revoked: [] } }')
            # 打开 A → 关闭 → 应 revoke
            page.locator('.el-table__row').first.locator('button:has-text("查看证件 / 审核")').click()
            page.wait_for_selector('.el-dialog:visible', timeout=5000)
            page.wait_for_timeout(400)
            page.locator('.el-dialog:visible button:has-text("关闭")').click()
            page.wait_for_timeout(600)
            log = blob_log(page)
            check(len(log['created']) == 1 and log['created'][0] in log['revoked'],
                  f'关闭弹窗应释放 Blob URL，探针: {log}')
            # 打开 B → 关闭 → 第二个也应 revoke（无残留）
            page.locator('.el-table__row').nth(1).locator('button:has-text("查看证件 / 审核")').click()
            page.wait_for_selector('.el-dialog:visible', timeout=5000)
            page.wait_for_timeout(400)
            page.locator('.el-dialog:visible button:has-text("关闭")').click()
            page.wait_for_timeout(600)
            log = blob_log(page)
            check(len(log['created']) == 2 and all(u in log['revoked'] for u in log['created']),
                  f'两次开关后不得残留未释放 Blob URL，探针: {log}')
            print(f'   [通过] created={len(log["created"])} revoked={len(log["revoked"])}，全部释放')
            record('V7_blob_url_cleanup', VP, 'PASS',
                   assertions={'created': len(log['created']), 'all_revoked': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('V7_blob_url_cleanup', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= V8 通过审核 =================
        print('\n--- V8 通过审核：核对项与请求体 ---')
        try:
            wait_msgs_gone(page)
            page.locator('.el-table__row').first.locator('button:has-text("查看证件 / 审核")').click()
            page.wait_for_selector('.el-dialog:visible', timeout=5000)
            posts_before = count_requests('POST', '/review')
            page.locator('.el-dialog:visible button:has-text("通过核验")').click()
            page.wait_for_timeout(600)
            check(count_requests('POST', '/review') == posts_before, '核对项不全不得发出请求')
            check('请完成全部核对项目' in msg_text(page), f'应有核对项提示，实际: 「{msg_text(page)}」')

            dlg = page.locator('.el-dialog:visible')
            dlg.locator('input').first.fill('20230101')
            for label in ['学生证与拍摄码同框且码一致', '学校与试点学校一致',
                          '学号清晰且为本人有效学生证', '已核对有效期（最长认证 12 个月）']:
                dlg.locator('.el-checkbox', has_text=label).first.click()
                page.wait_for_timeout(200)
            page.locator('.el-dialog:visible button:has-text("通过核验")').click()
            page.wait_for_timeout(1000)
            post = last_requests('POST', '/review')[0]
            body = post['body'] or {}
            check(body.get('decision') == 'approved' and body.get('student_id') == '20230101'
                  and body.get('challenge_matches') is True and body.get('school_matches') is True
                  and body.get('student_number_matches') is True and body.get('validity_checked') is True,
                  f'通过请求体不符: {body}')
            check('审核结果已保存' in msg_text(page), '应有成功提示')
            check(page.locator('.el-dialog:visible').count() == 0, '审核成功后弹窗应关闭')
            log = blob_log(page)
            if log['created']:
                check(all(u in log['revoked'] for u in log['created']),
                      f'审核成功后 Blob URL 应释放，探针: {log}')
            s = shot(page, 'sv-v8-approve.png')
            print('   [通过] 校验拦截零请求、请求体全字段正确、成功后关窗释放')
            record('V8_approve_flow', VP, 'PASS',
                   assertions={'validation_blocks': True, 'body': body, 'dialog_closed': True},
                   screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('V8_approve_flow', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= V9 拒绝审核 =================
        print('\n--- V9 拒绝审核：理由必填与请求体 ---')
        try:
            wait_msgs_gone(page)
            page.locator('.el-table__row').first.locator('button:has-text("查看证件 / 审核")').click()
            page.wait_for_selector('.el-dialog:visible', timeout=5000)
            posts_before = count_requests('POST', '/review')
            page.locator('.el-dialog:visible button:has-text("拒绝")').click()
            page.wait_for_timeout(600)
            check(count_requests('POST', '/review') == posts_before, '理由为空不得发出请求')
            check('请填写拒绝原因' in msg_text(page), f'应有理由提示，实际: 「{msg_text(page)}」')

            page.locator('.el-dialog:visible textarea').fill('照片模糊，无法辨认有效期')
            page.locator('.el-dialog:visible button:has-text("拒绝")').click()
            page.wait_for_timeout(1000)
            body = last_requests('POST', '/review')[0]['body'] or {}
            check(body.get('decision') == 'rejected' and body.get('reason') == '照片模糊，无法辨认有效期',
                  f'拒绝请求体不符: {body}')
            check('审核结果已保存' in msg_text(page), '拒绝成功应有提示')
            print('   [通过] 理由必填拦截零请求、拒绝请求体正确')
            record('V9_reject_flow', VP, 'PASS',
                   assertions={'reason_required': True, 'body': body})
        except Exception as e:
            print(f'   [失败] {e}')
            record('V9_reject_flow', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= V10 审核失败恢复 =================
        print('\n--- V10 审核业务错误/网络失败后 saving 释放与重试 ---')
        try:
            wait_msgs_gone(page)
            flags['review_error'] = True
            page.locator('.el-table__row').first.locator('button:has-text("查看证件 / 审核")').click()
            page.wait_for_selector('.el-dialog:visible', timeout=5000)
            page.locator('.el-dialog:visible textarea').fill('与其他记录重复')
            page.locator('.el-dialog:visible button:has-text("拒绝")').click()
            page.wait_for_timeout(800)
            check('该记录已被其他管理员处理' in msg_text(page),
                  f'业务错误应展示，实际: 「{msg_text(page)}」')
            btn_class = page.locator('.el-dialog:visible button:has-text("拒绝")').get_attribute('class') or ''
            check('is-loading' not in btn_class, '失败后 saving 应释放（按钮无 loading）')
            check(page.locator('.el-dialog:visible').count() >= 1, '失败后弹窗应保持打开可重试')
            flags['review_error'] = False
            page.locator('.el-dialog:visible button:has-text("拒绝")').click()
            page.wait_for_timeout(1000)
            check('审核结果已保存' in msg_text(page), '重试应成功')
            s = shot(page, 'sv-v10-error-retry.png')
            print('   [通过] 业务错误展示、saving 释放、弹窗保持、重试成功')
            record('V10_review_error_retry', VP, 'PASS',
                   assertions={'error_toast': True, 'saving_released': True, 'retry_ok': True},
                   screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('V10_review_error_retry', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            flags['review_error'] = False

        # ================= V11 撤销认证 =================
        print('\n--- V11 撤销认证：校验/取消/成功 ---')
        try:
            select_status(page, '已通过')
            # 取消 prompt：零 POST
            posts_before = count_requests('POST', '/revoke')
            page.locator('.el-table__row').first.locator('button:has-text("撤销认证")').click()
            page.wait_for_selector('.el-message-box', timeout=5000)
            page.locator('.el-message-box__btns button').first.click()  # 取消
            page.wait_for_timeout(600)
            check(count_requests('POST', '/revoke') == posts_before, '取消撤销不得发出 POST')
            check('认证已撤销' not in msg_text(page), '取消不得误报成功')

            # 理由过短：validator 拦截
            page.locator('.el-table__row').first.locator('button:has-text("撤销认证")').click()
            page.wait_for_selector('.el-message-box', timeout=5000)
            page.locator('.el-message-box input').fill('短')
            page.locator('.el-message-box__btns button').last.click()
            page.wait_for_timeout(500)
            check('至少输入 2 个字符' in page.locator('.el-message-box').inner_text(),
                  '理由校验应提示至少 2 字符')
            check(count_requests('POST', '/revoke') == posts_before, '校验失败不得发出 POST')
            page.locator('.el-message-box__btns button').first.click()
            page.wait_for_timeout(400)

            # 正常撤销
            revoked_name = page.locator('.el-table__row').first.locator('td').nth(0).inner_text().strip()
            page.locator('.el-table__row').first.locator('button:has-text("撤销认证")').click()
            page.wait_for_selector('.el-message-box', timeout=5000)
            page.locator('.el-message-box input').fill('重复申请，保留最新记录')
            page.locator('.el-message-box__btns button').last.click()
            page.wait_for_timeout(1000)
            body = last_requests('POST', '/revoke')[0]['body'] or {}
            check(body == {'reason': '重复申请，保留最新记录'}, f'撤销请求体不符: {body}')
            check('认证已撤销' in msg_text(page), '撤销成功应有提示')
            page.wait_for_timeout(1000)
            check(revoked_name not in page.locator('.el-table').inner_text(),
                  f'撤销后已通过列表应刷新剔除「{revoked_name}」，当前: {page.locator(".el-table").inner_text()[:120]}')
            s = shot(page, 'sv-v11-revoke.png')
            print('   [通过] 取消零 POST、理由校验拦截、请求体与刷新正确')
            record('V11_revoke_flow', VP, 'PASS',
                   assertions={'cancel_no_post': True, 'validator_blocks': True,
                               'body': body, 'list_refreshed': True}, screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('V11_revoke_flow', VP, 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        ctx.close()

        # ================= V12 响应式 =================
        for label, w, h in [('tablet-768', 768, 1024), ('narrow-390', 390, 844)]:
            print(f'\n--- V12 响应式 {label} ---')
            try:
                ctx2, page2 = new_admin_context(browser, w, h)
                page2.goto(route_url(base_url, '/student-verifications'))
                page2.wait_for_selector('.el-table__row', timeout=8000)
                page2.wait_for_timeout(600)
                m = doc_overflow(page2)
                check(m['sw'] <= m['cw'] + 2, f'{label} 页面横向溢出: {m}')
                page2.locator('button:has-text("查看证件 / 审核")').first.click()
                page2.wait_for_selector('.el-dialog:visible', timeout=5000)
                page2.wait_for_timeout(600)
                dlg = page2.locator('.el-dialog:visible').first.bounding_box()
                check(dlg['x'] >= 0 and dlg['x'] + dlg['width'] <= w + 1,
                      f'{label} 760px 核验弹窗超出视口: {dlg} (视口 {w})')
                for btn_text in ['拒绝', '通过核验']:
                    btn = page2.locator(f'.el-dialog:visible button:has-text("{btn_text}")')
                    check(btn.count() >= 1 and btn.first.is_visible(), f'{label} 按钮「{btn_text}」应可用')
                m2 = doc_overflow(page2)
                check(m2['sw'] <= m2['cw'] + 2, f'{label} 弹窗打开后页面横向溢出: {m2}')
                s = shot(page2, f'sv-v12-{label}.png')
                print(f'   [通过] {label} 无溢出，弹窗与按钮适配')
                record(f'V12_responsive_{label}', f'{w}x{h}', 'PASS',
                       assertions={'doc': m2, 'dialog': dlg, 'buttons_ok': True}, screenshots=[s])
                ctx2.close()
            except Exception as e:
                print(f'   [失败] {e}')
                record(f'V12_responsive_{label}', f'{w}x{h}', 'FAIL',
                       error=f'{e}\n{traceback.format_exc(limit=3)}')
                try:
                    shot(page2, f'sv-v12-{label}-fail.png')
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

report_path = f'{ARTIFACTS_DIR}/student-verifications-report.json'
with open(report_path, 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

passed = sum(1 for s in report['scenarios'] if s['status'] == 'PASS')
print(f'\n========================================================')
print(f'学生证认证页验收结束: {passed}/{len(report["scenarios"])} 场景通过，总体 {report["overall"]}')
print(f'报告: {report_path}')
print(f'========================================================')

if report['overall'] != 'PASS':
    sys.exit(1)
