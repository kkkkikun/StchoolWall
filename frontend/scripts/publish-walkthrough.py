#!/usr/bin/env python3
"""
SchoolWall 学生端 H5 发布页（pages/publish/index）真实浏览器验收
（独立脚本；复用 h5_mock_api.py 共享 Mock 与断言工具，单 Chromium 390x844 串行）

场景：
  P1 发布页加载：类型胶囊×4、标签、分类选择器、正文框、发布按钮可见，无横向溢出
  P2 空内容提交被拒绝：toast 提示且 POST /posts 零调用
  P3 合法内容 + 关键控件交互（标签点选写入正文、分类 ActionSheet 实际选择）→
     提交成功：恰好 1 次 POST、请求体含所选分类与标签、成功 toast、跳转首页
  P4 请求在途连点发布 ×3：仅 1 次 POST，内容不被清空
  P5 API 业务错误（code!=0）：错误 toast 原样展示、按钮恢复、重试成功
  P6 网络中断（abort）：toast 提示、按钮恢复、重试成功

Mock 登录态：localStorage user_info + sw_csrf Cookie（与 utils/storage.ts web 分支
isLoggedIn 契约一致：csrfCookie() && getUserInfo()）。不访问真实后端。
请求计数与请求体来自 Playwright 实际拦截的 HTTP 请求。
产物：ci-artifacts/ui-walkthrough/publish-walkthrough-report.json + publish-*.png
任一断言失败 -> 场景 FAIL，脚本退出码非零。
"""

import json
import os
import sys
import time
import traceback
from playwright.sync_api import sync_playwright

from h5_walkthrough_server import create_server

from h5_mock_api import handle_api, assert_no_horizontal_overflow

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIST_DIR = os.path.join(ROOT_DIR, 'frontend', 'dist', 'build', 'h5')
ARTIFACTS_DIR = os.path.join(ROOT_DIR, 'ci-artifacts', 'ui-walkthrough')
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

if not os.path.isdir(DIST_DIR):
    print(f"Error: DIST_DIR not found at {DIST_DIR}. Run 'npm run build:h5' first.", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------- 静态服务
httpd, base_url = create_server(DIST_DIR)
print(f'H5 static server listening on {base_url}')

# ---------------------------------------------------------------- Mock 状态
TAGS_FIXTURE = [{'id': 1, 'name': '考研'}, {'id': 2, 'name': '夜跑'}]
SESSION_OK = {
    'code': 0, 'message': 'success',
    'data': {
        'access_token': 'mock-access-token-for-publish-test',
        'csrf_token': 'mock-csrf-token',
        'session_id': 'mock-session-id',
        'role': 'guest',
        'user_info': {'id': 'u-pub-test', 'nickname': '发布测试同学', 'is_verified': False},
    },
}
post_calls = {'count': 0, 'bodies': []}
held_post_routes = []
post_behavior = {'mode': 'ok'}  # ok | hold | error | abort

def handle_web_login(route):
    """真实 UI 登录流程的 Mock 响应（契约同 services/sessions.py session_payload）。"""
    route.fulfill(status=200, content_type='application/json', body=json.dumps(SESSION_OK))

def handle_profile(route):
    """登录后 loadProfile 拉取资料：必须 200，否则共享兜底对 /user/profile 的 401
    会触发 request.ts 的会话清理，把刚建立的登录态踢掉。"""
    route.fulfill(status=200, content_type='application/json', body=json.dumps({
        'code': 0, 'data': {'nickname': '发布测试同学', 'is_verified': False}}))

def handle_tags(route):
    route.fulfill(status=200, content_type='application/json',
                  body=json.dumps({'code': 0, 'data': TAGS_FIXTURE}))

def handle_posts(route):
    if route.request.method != 'POST':
        return handle_api(route)
    post_calls['count'] += 1
    try:
        post_calls['bodies'].append(json.loads(route.request.post_data or '{}'))
    except Exception:
        post_calls['bodies'].append(None)
    mode = post_behavior['mode']
    if mode == 'hold':
        held_post_routes.append(route)
        return
    if mode == 'abort':
        route.abort()
        return
    if mode == 'error':
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps({'code': 400, 'message': '内容包含敏感词，请修改后重试'}))
        return
    route.fulfill(status=200, content_type='application/json',
                  body=json.dumps({'code': 0, 'data': {'post_id': 9001, 'status': 0}}))

def release_held_posts(as_success=True):
    routes = held_post_routes[:]
    held_post_routes.clear()
    for r in routes:
        try:
            if as_success:
                r.fulfill(status=200, content_type='application/json',
                          body=json.dumps({'code': 0, 'data': {'post_id': 9001, 'status': 0}}))
            else:
                r.fulfill(status=200, content_type='application/json',
                          body=json.dumps({'code': 400, 'message': '内容包含敏感词'}))
        except Exception:
            pass
    return len(routes)

# ---------------------------------------------------------------- 工具
class ScenarioFailure(Exception):
    pass

def check(cond, msg):
    if not cond:
        raise ScenarioFailure(msg)

report = {
    'task': 'student H5 publish page acceptance',
    'date_utc': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
    'base_url': base_url,
    'browser': 'chromium(headless)',
    'viewport': '390x844',
    'mock_scope': '**/api/v1/** local interception; POST /posts counted & captured; mocked login state (localStorage user_info + sw_csrf cookie). No real backend.',
    'post_requests': post_calls,
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

def set_content(page, text):
    """uni-textarea 内层原生 textarea 赋值 + input 事件（驱动 v-model/:value 数据流）。"""
    page.evaluate('''(v) => {
        const t = document.querySelector('.post-textarea textarea') ||
                  document.querySelector('.post-textarea');
        t.value = v;
        t.dispatchEvent(new Event('input', { bubbles: true }));
    }''', text)
    page.wait_for_timeout(150)

def get_content(page):
    return page.evaluate('''() => {
        const t = document.querySelector('.post-textarea textarea') ||
                  document.querySelector('.post-textarea');
        return t.value;
    }''')

def goto_publish(page):
    """经底部 TabBar「发布」进行应用内导航（同文档 SPA，保留内存会话）。
    注意：本 H5 构建的 uni 存储为内存态，page.goto 整页刷新会丢失登录态。"""
    if 'pages/publish/index' in page.url and page.locator('.publish-btn').count():
        page.wait_for_timeout(300)
        return
    page.locator('.tab-bar .tab-item').nth(2).click()
    page.wait_for_selector('.publish-btn', timeout=8000)
    page.wait_for_timeout(500)

def login_via_ui(page):
    """通过真实 UI 登录弹窗 + Mock API 建立会话（生产 storeLoginSession 写入内存令牌），
    替代手工构造 storage——window.uni 在 H5 构建中非完整 API 面，直接写 localStorage 不可靠。"""
    page.goto(f'{base_url}/#/pages/mine/index')
    page.wait_for_selector('.dev-login-row', timeout=8000)
    page.locator('.dev-capsule:has-text("登录 / 注册")').click()
    page.wait_for_selector('.auth-form', timeout=5000)
    page.evaluate('''() => {
        const inputs = document.querySelectorAll('.auth-form .auth-input input');
        ['publish_tester', 'password123'].forEach((v, i) => {
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

def assert_back_home(page):
    """uni-app H5 reLaunch 到 tabBar 页后地址栏哈希规范化为 '#/'，
    因此以首页专属内容断言跳转结果，而非 URL 字符串。"""
    page.wait_for_selector('.feed-card', timeout=8000)
    if page.locator('.publish-btn').count() > 0:
        raise ScenarioFailure('跳转后仍停留在发布页')

exit_code = 0
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={'width': 390, 'height': 844})
        page = ctx.new_page()
        page.route('**/api/v1/**', handle_api)      # 兜底先注册（Playwright 后注册优先）
        page.route('**/api/v1/tags', handle_tags)
        page.route('**/api/v1/posts', handle_posts)
        page.route('**/api/v1/auth/web-login', handle_web_login)
        page.route('**/api/v1/user/profile', handle_profile)

        # 通过真实 UI + Mock 后端完成登录，建立内存会话（同一文档后续 hash 导航保持登录态）
        login_via_ui(page)

        # ================= P1 加载与布局 =================
        print('\n--- P1 发布页加载与布局 ---')
        try:
            goto_publish(page)
            check(page.locator('.type-pill').count() == 4, '类型胶囊应为 4 个')
            check(page.locator('.tag-badge').count() == 2, '热搜标签应渲染 2 个（Mock）')
            check(page.locator('.section-selector').is_visible(), '分类选择器应可见')
            check(page.locator('.selector-title').inner_text().strip() == '广场', '默认分类应为「广场」')
            check(page.locator('.upload-box').is_visible(), '图片上传入口应可见')
            check(page.locator('.publish-btn').is_visible(), '发布按钮应可见')
            assert_no_horizontal_overflow(page, '发布页 390x844')
            s = shot(page, 'publish-p1-light.png')
            print('   [通过] 控件齐全，无横向溢出')
            record('P1_load_layout', 'PASS',
                   assertions={'type_pills': 4, 'tags': 2, 'default_section': '广场',
                               'overflow': False}, screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('P1_load_layout', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= P2 空内容拒绝 =================
        print('\n--- P2 空内容提交拒绝 ---')
        try:
            before = post_calls['count']
            page.locator('.publish-btn').click()
            page.wait_for_timeout(600)
            check(post_calls['count'] == before, f'空内容不得发出 POST /posts，计数变化: {before} -> {post_calls["count"]}')
            t = toast_text(page)
            check('内容' in t, f'应有内容校验提示，实际 toast: 「{t}」')
            print(f'   [通过] 零请求，toast=「{t}」')
            record('P2_empty_rejected', 'PASS',
                   assertions={'post_requests_delta': 0, 'toast': t})
        except Exception as e:
            print(f'   [失败] {e}')
            record('P2_empty_rejected', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= P3 合法提交 + 控件交互 =================
        print('\n--- P3 合法提交（标签点选 + 分类选择） ---')
        try:
            set_content(page, '出九成新考研英语真题，附笔记')
            page.locator('.tag-badge').first.click()
            page.wait_for_timeout(300)
            check('#考研' in get_content(page), f'标签点选应写入正文，实际: {get_content(page)}')

            page.locator('.section-selector').click()
            page.wait_for_timeout(500)
            page.locator('.uni-actionsheet__cell:has-text("失物")').first.click()
            page.wait_for_timeout(300)
            check(page.locator('.selector-title').inner_text().strip() == '失物', '分类应切换为「失物」')
            s = shot(page, 'publish-p3-ready.png')

            post_behavior['mode'] = 'ok'
            before = post_calls['count']
            page.locator('.publish-btn').click()
            page.wait_for_timeout(1000)
            check(post_calls['count'] - before == 1, '应恰好 1 次 POST /posts')
            body = post_calls['bodies'][-1]
            check(body and body.get('category') == '失物', f'请求体分类应为「失物」，实际: {body}')
            check('#考研' in (body.get('content') or ''), f'请求体正文应含标签，实际: {body}')
            check(body.get('post_type') == 'general', f'post_type 应为 general，实际: {body}')
            t = toast_text(page)
            check('发布成功' in t, f'应有成功提示，实际: 「{t}」')
            page.wait_for_timeout(1500)
            assert_back_home(page)
            print(f'   [通过] 1 次 POST，分类=失物，正文含 #考研，跳转 {page.url}')
            record('P3_submit_success', 'PASS',
                   assertions={'post_requests_delta': 1, 'request_body': body,
                               'toast': t, 'redirected_to_home': True}, screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('P3_submit_success', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= P4 在途防重 =================
        print('\n--- P4 请求在途连点防重 ---')
        try:
            goto_publish(page)
            set_content(page, '周末图书馆组队自习，有意向评论区留言')
            post_behavior['mode'] = 'hold'
            before = post_calls['count']
            for _ in range(3):
                page.locator('.publish-btn').click()
                page.wait_for_timeout(250)
            check(post_calls['count'] - before == 1,
                  f'连点 3 次应只 1 次 POST，实际 {post_calls["count"] - before}')
            check(get_content(page) != '', '在途期间内容不得被清空')
            s = shot(page, 'publish-p4-inflight.png')
            release_held_posts(as_success=True)
            page.wait_for_timeout(1800)
            assert_back_home(page)
            print('   [通过] 在途连点仅 1 次请求，放行后跳转')
            record('P4_inflight_dedup', 'PASS',
                   assertions={'clicks': 3, 'post_requests_delta': 1,
                               'content_kept_inflight': True}, screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('P4_inflight_dedup', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            release_held_posts()
            post_behavior['mode'] = 'ok'

        # ================= P5 API 业务错误恢复 =================
        print('\n--- P5 API 业务错误后恢复重试 ---')
        try:
            goto_publish(page)
            set_content(page, '求购二手自行车一辆，预算两百以内')
            post_behavior['mode'] = 'error'
            before = post_calls['count']
            page.locator('.publish-btn').click()
            page.wait_for_timeout(800)
            check(post_calls['count'] - before == 1, '错误场景应恰好 1 次请求')
            t = toast_text(page)
            check('敏感词' in t, f'应展示后端错误提示，实际: 「{t}」')
            check(get_content(page) != '', '失败后表单内容应保留')
            s = shot(page, 'publish-p5-error.png')

            post_behavior['mode'] = 'ok'
            page.locator('.publish-btn').click()
            page.wait_for_timeout(1800)
            check(post_calls['count'] - before == 2, '重试应产生第 2 次请求')
            assert_back_home(page)
            print(f'   [通过] 错误 toast=「{t}」，重试成功跳转')
            record('P5_api_error_retry', 'PASS',
                   assertions={'error_toast': t, 'retry_requests': 2, 'form_kept': True},
                   screenshots=[s])
        except Exception as e:
            print(f'   [失败] {e}')
            record('P5_api_error_retry', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            post_behavior['mode'] = 'ok'

        # ================= P6 网络中断恢复 =================
        print('\n--- P6 网络中断后恢复重试 ---')
        try:
            goto_publish(page)
            set_content(page, '失物招领：三教捡到一串钥匙')
            post_behavior['mode'] = 'abort'
            before = post_calls['count']
            page.locator('.publish-btn').click()
            page.wait_for_timeout(800)
            check(post_calls['count'] - before == 1, 'abort 场景应恰好 1 次请求')
            t = toast_text(page)
            check(t == '网络连接失败，请检查网络后重试',
                  f'网络失败应映射为友好提示，实际: 「{t}」')
            check('request:fail' not in t, f'底层 request:fail 不得直接展示，实际: 「{t}」')
            check('pages/publish' in page.url, '网络失败后应停留在发布页')

            post_behavior['mode'] = 'ok'
            page.locator('.publish-btn').click()
            page.wait_for_timeout(1800)
            check(post_calls['count'] - before == 2, '重试应产生第 2 次请求')
            assert_back_home(page)
            print(f'   [通过] 网络中断 toast=「{t}」，重试成功跳转')
            record('P6_network_abort_retry', 'PASS',
                   assertions={'abort_toast': t, 'retry_success': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('P6_network_abort_retry', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            post_behavior['mode'] = 'ok'

        ctx.close()
        browser.close()
except Exception as e:
    print(f'\n[致命错误] {e}', file=sys.stderr)
    report['overall'] = 'FAIL'
    report['fatal'] = f'{e}\n{traceback.format_exc(limit=3)}'
finally:
    httpd.shutdown()

report_path = f'{ARTIFACTS_DIR}/publish-walkthrough-report.json'
with open(report_path, 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

passed = sum(1 for s in report['scenarios'] if s['status'] == 'PASS')
print(f'\n========================================================')
print(f'发布页验收结束: {passed}/{len(report["scenarios"])} 场景通过，总体 {report["overall"]}')
print(f'POST /posts 实际拦截计数: {post_calls["count"]}')
print(f'报告: {report_path}')
print(f'========================================================')

if report['overall'] != 'PASS':
    sys.exit(1)
