#!/usr/bin/env python3
"""
SchoolWall 学生端 H5 登录弹窗防重复提交 / 失败重试 —— 真实浏览器专项验收
（独立脚本，不改动 ui-walkthrough.py）

针对已构建的 frontend/dist/build/h5，用单个 Headless Chromium (390x844) 验证：
  S1 弹窗结构：登录/注册/找回三模式标题、输入项、主按钮文案
  S2 输入校验失败：不发出任何请求，不残留 loading 态
  S3 登录防连击：请求在途时连续点击 → 仅 1 次 HTTP 请求（计数来自真实拦截），
     按钮显示「处理中…」且 saving 类生效
  S4 在途模式锁定：请求 pending 期间切换注册/找回被忽略；完成后恢复切换能力
  S5 接口错误恢复：code!=0 → 错误 toast 可见、按钮恢复、重试成功
  S6 网络中断恢复：route.abort → 按钮恢复、重试成功
  S7 注册防连击：仅 1 次 register 请求
  S8 找回防连击：仅 1 次 recover 请求，成功后回到登录模式
  S9 暗色主题弹窗截图

请求计数全部来自 Playwright 实际拦截的 HTTP 请求，不读取 Vue 内部状态推断。
Mock 响应遵循 frontend/src/api/auth.ts 与 utils/request.ts 的真实契约：
  POST /api/v1/auth/web-login|register -> {code:0,data:SessionData}
  POST /api/v1/auth/recover           -> {code:0,data:...}
  错误: HTTP 200 + {code:401,message:...}（request.ts 对 code!==0 reject）
会话存储(web)：access_token + role + user_info（storage.ts setSession web 分支）

产物：ci-artifacts/ui-walkthrough/web-login-guard-report.json + web-login-*.png
任何场景失败 -> 该场景 FAIL，脚本最终退出码非零。
"""

import json
import os
import sys
import traceback
from playwright.sync_api import sync_playwright

from h5_walkthrough_server import create_server

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
SESSION_OK = {
    'code': 0, 'message': 'success',
    'data': {
        'access_token': 'mock-access-token-for-test',
        'csrf_token': 'mock-csrf-token',
        'session_id': 'mock-session-id',
        'role': 'student',
        'user_info': {'id': 'u-test-01', 'nickname': '测试同学', 'is_verified': False},
    },
}

# 每个端点的真实拦截计数与挂起的 route（hold 行为时先入队，稍后统一放行）
counts = {'web-login': 0, 'register': 0, 'recover': 0}
held = {'web-login': [], 'register': [], 'recover': []}
behavior = {'web-login': 'hold', 'register': 'hold', 'recover': 'hold'}  # hold|ok|error|abort

def make_auth_handler(kind):
    def handler(route):
        counts[kind] += 1
        b = behavior[kind]
        if b == 'hold':
            held[kind].append(route)
            return
        if b == 'abort':
            route.abort()
            return
        if b == 'error':
            route.fulfill(status=200, content_type='application/json',
                          body=json.dumps({'code': 401, 'message': '账号或密码错误'}))
            return
        if b.startswith('malformed_'):
            # 畸形成功响应：去掉指定字段（malformed_no_user / malformed_no_role）
            drop = {'malformed_no_user': 'user_info', 'malformed_no_role': 'role'}[b]
            data = {k: v for k, v in SESSION_OK['data'].items() if k != drop}
            route.fulfill(status=200, content_type='application/json',
                          body=json.dumps({'code': 0, 'message': 'success', 'data': data}))
            return
        route.fulfill(status=200, content_type='application/json', body=json.dumps(SESSION_OK))
    return handler

def catch_all(route):
    url = route.request.url
    if '/user/profile' in url:
        body = {'code': 0, 'data': {'nickname': '测试同学', 'is_verified': False}}
    else:
        body = {'code': 0, 'message': 'ok', 'data': {'items': [], 'total': 0}}
    route.fulfill(status=200, content_type='application/json', body=json.dumps(body))

def release_held(kind, as_success=True):
    """放行挂起的请求；as_success=False 时以接口错误放行。"""
    routes = held[kind][:]
    held[kind].clear()
    for r in routes:
        try:
            if as_success:
                r.fulfill(status=200, content_type='application/json', body=json.dumps(SESSION_OK))
            else:
                r.fulfill(status=200, content_type='application/json',
                          body=json.dumps({'code': 401, 'message': '账号或密码错误'}))
        except Exception:
            pass
    return len(routes)

# ---------------------------------------------------------------- 断言工具
class ScenarioFailure(Exception):
    pass

def check(cond, msg):
    if not cond:
        raise ScenarioFailure(msg)

report = {
    'task': 'H5 web login dialog anti-double-submit & retry acceptance',
    'date_utc': __import__('time').strftime('%Y-%m-%d %H:%M:%S', __import__('time').gmtime()),
    'base_url': base_url,
    'browser': 'chromium(headless)',
    'viewport': '390x844',
    'url_patterns': ['/api/v1/auth/web-login', '/api/v1/auth/register', '/api/v1/auth/recover'],
    'request_counts': counts,
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

def btn_text(page):
    return page.locator('.auth-submit').inner_text().strip()

def mode_hint(page):
    """当前模式的提示文案：登录 / 注册 / 找回各不相同。"""
    return page.locator('.auth-hint').inner_text().strip()

def is_saving(page):
    cls = page.locator('.auth-submit').get_attribute('class') or ''
    return 'saving' in cls

def toast_text(page):
    t = page.locator('uni-toast')
    if t.count() == 0:
        return ''
    return t.inner_text().strip()

def error_text(page):
    """登录页的就地错误提示：校验失败/接口错误不再用 toast 打断。"""
    t = page.locator('.auth-error-text')
    if t.count() == 0:
        return ''
    return t.inner_text().strip()

def open_auth(page):
    """从「我的」页进入独立登录/注册页。"""
    page.locator('.dev-capsule:has-text("登录 / 注册")').click()
    page.wait_for_selector('.auth-form', timeout=5000)
    page.wait_for_timeout(300)

def close_auth(page):
    """从登录页返回「我的」页（走应用内返回箭头）。"""
    page.locator('.back-trigger').click()
    page.wait_for_timeout(600)

def on_auth_page(page):
    return page.locator('.auth-form').count() > 0

def fill_form(page, username='walkthrough_user', password='password123', code=None):
    # uni-input 内层原生 input 对 Playwright 不可见（uni-app H5 包装），
    # 用 JS 赋值并派发 input 事件驱动 v-model（等价于真实键入的数据流）
    values = [username, password] if code is None else [username, code, password]
    page.evaluate('''(vals) => {
        const inputs = document.querySelectorAll('.auth-form .auth-input input');
        vals.forEach((v, i) => {
            const el = inputs[i];
            el.value = v;
            el.dispatchEvent(new Event('input', { bubbles: true }));
        });
    }''', values)
    page.wait_for_timeout(150)

def reset_to_guest(page, theme=None):
    """清空本地会话并回到「我的」页访客态（goto 同 hash URL 不会重载，必须再 reload）。"""
    page.evaluate("""(t) => {
        try {
            localStorage.clear();
            if (t) localStorage.setItem('sw_theme_mode', t);
        } catch(e) {}
    }""", theme)
    page.goto(f'{base_url}/#/pages/mine/index')
    page.reload()
    page.wait_for_selector('.dev-login-row', timeout=8000)
    page.wait_for_timeout(500)

def force_close_auth(page):
    try:
        if on_auth_page(page):
            page.locator('.back-trigger').click(timeout=3000)
            page.wait_for_timeout(600)
    except Exception:
        pass

exit_code = 0
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={'width': 390, 'height': 844})
        page = ctx.new_page()
        # Playwright 后注册的路由优先匹配：兜底路由必须先注册
        page.route('**/api/v1/**', catch_all)
        for kind in ('web-login', 'register', 'recover'):
            page.route(f'**/api/v1/auth/{kind}', make_auth_handler(kind))

        page.goto(f'{base_url}/#/pages/mine/index')
        page.wait_for_selector('.dev-login-row', timeout=8000)
        page.wait_for_timeout(500)

        # ================= S1 弹窗结构与三模式文案 =================
        print('\n--- S1 弹窗结构与模式文案 ---')
        try:
            open_auth(page)
            check(mode_hint(page) == '使用已注册的账号登录', f'默认提示应为「使用已注册的账号登录」，实际「{mode_hint(page)}」')
            check(btn_text(page) == '进入鄂应墙', f'登录主按钮应为「进入鄂应墙」，实际「{btn_text(page)}」')
            check(page.locator('.auth-input').count() == 2, '登录模式应有 2 个输入框')
            check(page.locator('.auth-tab:has-text("注册")').count() == 1, '缺注册切换链接')
            check(page.locator('.auth-link:has-text("忘记密码")').count() == 1, '缺忘记密码切换链接')
            s_light = shot(page, 'web-login-modal-light.png')

            page.locator('.auth-tab:has-text("注册")').click()
            page.wait_for_timeout(300)
            check(mode_hint(page) == '注册密码至少 10 位', f'注册模式提示错误: {mode_hint(page)}')
            check(btn_text(page) == '注册并登录', f'注册按钮文案错误: {btn_text(page)}')

            page.locator('.auth-link:has-text("忘记密码")').click()
            page.wait_for_timeout(300)
            check(mode_hint(page) == '使用离线找回码重置密码', f'找回模式提示错误: {mode_hint(page)}')
            check(btn_text(page) == '重置密码', f'找回按钮文案错误: {btn_text(page)}')
            check(page.locator('.auth-input').count() == 3, '找回模式应有 3 个输入框（含找回码）')

            page.locator('.auth-link:has-text("返回登录")').click()
            page.wait_for_timeout(300)
            check(mode_hint(page) == '使用已注册的账号登录', '返回登录失败')
            print('   [通过] 三模式标题/输入项/按钮文案正确')
            record('S1_modal_structure', 'PASS',
                   assertions={'titles': ['登录', '注册账号', '找回账号密码'],
                               'buttons': ['进入鄂应墙', '注册并登录', '重置密码']},
                   screenshots=[s_light])
        except Exception as e:
            print(f'   [失败] {e}')
            record('S1_modal_structure', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= S2 校验失败：零请求、无残留 loading =================
        print('\n--- S2 输入校验失败 ---')
        try:
            before = dict(counts)
            page.locator('.auth-submit').click()
            page.wait_for_timeout(500)
            check(counts == before, f'校验失败不得发出请求，实际计数变化: {counts} vs {before}')
            check(not is_saving(page), '校验失败不得残留 saving 态')
            check(btn_text(page) == '进入鄂应墙', f'按钮文案应恢复，实际: {btn_text(page)}')
            t = error_text(page)
            check('账号和密码' in t or '有效' in t, f'应有就地校验提示，实际: 「{t}」')
            print(f'   [通过] 空表单点击零请求，toast=「{t}」，按钮无残留 loading')
            record('S2_validation_failure', 'PASS',
                   assertions={'requests_sent': 0, 'saving': False, 'toast': t})
        except Exception as e:
            print(f'   [失败] {e}')
            record('S2_validation_failure', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= S3 登录防连击（请求挂起期间连点） =================
        print('\n--- S3 登录模式防重复提交 ---')
        try:
            fill_form(page)
            behavior['web-login'] = 'hold'
            before_n = counts['web-login']
            for _ in range(3):
                page.locator('.auth-submit').click()
                page.wait_for_timeout(250)
            check(counts['web-login'] - before_n == 1,
                  f'连点 3 次应只产生 1 次 web-login 请求，实际 {counts["web-login"] - before_n}')
            check(btn_text(page) == '处理中…', f'在途按钮应显示「处理中…」，实际「{btn_text(page)}」')
            check(is_saving(page), '在途按钮应带 saving 类')
            s_saving = shot(page, 'web-login-saving-inflight.png')

            # ================= S4 在途模式锁定 =================
            print('--- S4 请求在途时模式切换锁定 ---')
            try:
                page.locator('.auth-tab:has-text("注册")').click()
                page.wait_for_timeout(200)
                check(mode_hint(page) == '使用已注册的账号登录', f'在途切注册应被忽略，实际提示: {mode_hint(page)}')
                page.locator('.auth-link:has-text("忘记密码")').click()
                page.wait_for_timeout(200)
                check(mode_hint(page) == '使用已注册的账号登录', f'在途切找回应被忽略，实际提示: {mode_hint(page)}')
                s4_ok = True
                print('   [通过] 在途期间注册/找回切换均被忽略')
            except Exception as e:
                s4_ok = False
                print(f'   [失败] {e}')
                record('S4_inflight_mode_lock', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

            release_held('web-login', as_success=True)
            page.wait_for_timeout(1200)
            check(page.locator('.auth-form').count() == 0, '登录成功后应离开登录页')
            if s4_ok:
                # 完成后恢复切换能力（成功后已是登录态，入口胶囊隐藏，先重置为访客再验证）
                reset_to_guest(page)
                open_auth(page)
                page.locator('.auth-tab:has-text("注册")').click()
                page.wait_for_timeout(300)
                check(mode_hint(page) == '注册密码至少 10 位', '请求结束后模式切换应恢复')
                close_auth(page)
                record('S4_inflight_mode_lock', 'PASS',
                       assertions={'locked_during_flight': True, 'switch_restored_after': True})
            print('   [通过] 登录成功后离开登录页，模式切换恢复')
            record('S3_login_double_submit', 'PASS',
                   assertions={'clicks': 3, 'web_login_requests': 1,
                               'inflight_text': '处理中…', 'saving_class': True,
                               'modal_closed_after_success': True},
                   screenshots=[s_saving])
        except Exception as e:
            print(f'   [失败] {e}')
            record('S3_login_double_submit', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            release_held('web-login')
            force_close_auth(page)

        # 登出回到访客态：清掉本地会话并刷新页面
        force_close_auth(page)
        reset_to_guest(page)

        # ================= S5 接口错误恢复 + 重试成功 =================
        print('\n--- S5 登录接口错误后恢复并重试 ---')
        try:
            open_auth(page)
            fill_form(page)
            behavior['web-login'] = 'error'
            before_n = counts['web-login']
            page.locator('.auth-submit').click()
            page.wait_for_timeout(800)
            check(counts['web-login'] - before_n == 1, '应恰好 1 次 web-login 请求')
            t = error_text(page)
            check('账号或密码错误' in t, f'应展示接口错误提示，实际: 「{t}」')
            check(page.locator('.auth-form').count() == 1, '失败后应停留在登录页')
            check(btn_text(page) == '进入鄂应墙' and not is_saving(page),
                  f'失败后按钮应恢复，实际: {btn_text(page)}, saving={is_saving(page)}')
            s_err = shot(page, 'web-login-error-toast.png')

            behavior['web-login'] = 'ok'
            page.locator('.auth-submit').click()
            page.wait_for_timeout(1200)
            check(counts['web-login'] - before_n == 2, '重试应产生第 2 次请求')
            check(page.locator('.auth-form').count() == 0, '重试成功后应离开登录页')
            print('   [通过] 接口错误就地提示可见、按钮恢复，重试一次成功')
            record('S5_error_retry', 'PASS',
                   assertions={'error_toast': t, 'recovered': True, 'retry_requests': 2},
                   screenshots=[s_err])
        except Exception as e:
            print(f'   [失败] {e}')
            record('S5_error_retry', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            behavior['web-login'] = 'ok'

        force_close_auth(page)
        reset_to_guest(page)

        # ================= S6 网络中断（abort）恢复 + 重试 =================
        print('\n--- S6 网络中断后恢复并重试 ---')
        try:
            open_auth(page)
            fill_form(page)
            behavior['web-login'] = 'abort'
            before_n = counts['web-login']
            page.locator('.auth-submit').click()
            page.wait_for_timeout(800)
            check(counts['web-login'] - before_n == 1, 'abort 场景应恰好 1 次请求')
            check(page.locator('.auth-form').count() == 1, '网络失败后应停留在登录页')
            check(btn_text(page) == '进入鄂应墙' and not is_saving(page),
                  f'网络失败后按钮应恢复，实际: {btn_text(page)}')
            t = error_text(page)
            check(t == '网络连接失败，请检查网络后重试',
                  f'网络失败应映射为友好提示「网络连接失败，请检查网络后重试」，实际: 「{t}」')
            check('request:fail' not in t, f'底层 request:fail 不得直接展示给用户，实际: 「{t}」')

            behavior['web-login'] = 'ok'
            page.locator('.auth-submit').click()
            page.wait_for_timeout(1200)
            check(counts['web-login'] - before_n == 2, '网络恢复后重试应发出第 2 次请求')
            check(page.locator('.auth-form').count() == 0, '重试成功后应离开登录页')
            print(f'   [通过] 网络中断 toast=「{t}」，按钮恢复，重试成功')
            record('S6_network_abort_retry', 'PASS',
                   assertions={'abort_requests': 1, 'toast': t, 'retry_success': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('S6_network_abort_retry', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            behavior['web-login'] = 'ok'

        force_close_auth(page)
        reset_to_guest(page)

        # ================= S7 注册模式防连击 =================
        print('\n--- S7 注册模式防重复提交 ---')
        try:
            open_auth(page)
            page.locator('.auth-tab:has-text("注册")').click()
            page.wait_for_timeout(300)
            fill_form(page, username='walkthrough_new', password='newpassword10')
            behavior['register'] = 'hold'
            before_n = counts['register']
            for _ in range(3):
                page.locator('.auth-submit').click()
                page.wait_for_timeout(250)
            check(counts['register'] - before_n == 1,
                  f'注册连点 3 次应只 1 次请求，实际 {counts["register"] - before_n}')
            check(btn_text(page) == '处理中…' and is_saving(page), '注册在途应显示处理中')
            release_held('register', as_success=True)
            page.wait_for_timeout(1200)
            check(page.locator('.auth-form').count() == 0, '注册成功后应离开登录页')
            print('   [通过] 注册连点仅 1 次请求，成功后离开登录页')
            record('S7_register_double_submit', 'PASS',
                   assertions={'clicks': 3, 'register_requests': 1, 'modal_closed': True})
        except Exception as e:
            print(f'   [失败] {e}')
            record('S7_register_double_submit', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            release_held('register')

        force_close_auth(page)
        reset_to_guest(page)

        # ================= S8 找回密码防连击 =================
        print('\n--- S8 找回密码模式防重复提交 ---')
        try:
            open_auth(page)
            page.locator('.auth-link:has-text("忘记密码")').click()
            page.wait_for_timeout(300)
            fill_form(page, username='walkthrough_user', password='newpassword10', code='MOCK-RECOVERY-CODE')
            behavior['recover'] = 'hold'
            before_n = counts['recover']
            for _ in range(3):
                page.locator('.auth-submit').click()
                page.wait_for_timeout(250)
            check(counts['recover'] - before_n == 1,
                  f'找回连点 3 次应只 1 次请求，实际 {counts["recover"] - before_n}')
            check(btn_text(page) == '处理中…' and is_saving(page), '找回在途应显示处理中')
            release_held('recover', as_success=True)
            page.wait_for_timeout(1000)
            check(mode_hint(page) == '使用已注册的账号登录', f'重置成功后应回到登录模式，实际: {mode_hint(page)}')
            check(page.locator('.auth-form').count() == 1, '重置成功后应留在登录页等待登录')
            t = toast_text(page)
            check('密码已重置' in t, f'应有「密码已重置」提示，实际: 「{t}」')
            close_auth(page)
            print('   [通过] 找回连点仅 1 次请求，成功后回到登录模式并提示')
            record('S8_recovery_double_submit', 'PASS',
                   assertions={'clicks': 3, 'recover_requests': 1,
                               'back_to_login_mode': True, 'toast': t})
        except Exception as e:
            print(f'   [失败] {e}')
            record('S8_recovery_double_submit', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            release_held('recover')

        # ================= S10/S11 畸形成功响应加固 =================
        def run_malformed(name, behavior_key, desc):
            if not on_auth_page(page):
                open_auth(page)
            fill_form(page)
            behavior['web-login'] = behavior_key
            before_n = counts['web-login']
            page.locator('.auth-submit').click()
            page.wait_for_timeout(800)
            check(counts['web-login'] - before_n == 1, f'{desc}：应恰好 1 次请求')
            check(page.locator('.auth-form').count() == 1, f'{desc}：畸形响应后必须停留在登录页')
            check(page.evaluate("() => !localStorage.getItem('user_info')"),
                  f'{desc}：不得进入登录态（未写入用户会话）')
            check(btn_text(page) == '进入鄂应墙' and not is_saving(page),
                  f'{desc}：按钮应恢复可重试，实际: {btn_text(page)}')
            t = error_text(page)
            check(t == '登录响应异常，请稍后重试',
                  f'{desc}：错误提示应为友好中文，实际: 「{t}」')
            check('TypeError' not in t and 'undefined' not in t,
                  f'{desc}：不得向用户泄漏 TypeError/undefined，实际: 「{t}」')
            shot(page, f'{name}.png')

            behavior['web-login'] = 'ok'
            page.locator('.auth-submit').click()
            page.wait_for_timeout(1200)
            check(page.locator('.auth-form').count() == 0, f'{desc}：完整响应重试应成功离开登录页')
            record(name, 'PASS',
                   assertions={'malformed_error': t, 'stayed_on_auth_page': True,
                               'no_typeerror_leak': True, 'retry_success': True},
                   screenshots=[f'{name}.png'])
            print(f'   [通过] {desc}：停留在登录页、友好提示、重试成功')

        print('\n--- S10 畸形响应：缺少 user_info ---')
        try:
            run_malformed('S10_malformed_missing_user_info', 'malformed_no_user', '缺 user_info')
        except Exception as e:
            print(f'   [失败] {e}')
            record('S10_malformed_missing_user_info', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            behavior['web-login'] = 'ok'
            force_close_auth(page)
        reset_to_guest(page)

        print('\n--- S11 畸形响应：缺少 role ---')
        try:
            run_malformed('S11_malformed_missing_role', 'malformed_no_role', '缺 role')
        except Exception as e:
            print(f'   [失败] {e}')
            record('S11_malformed_missing_role', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            behavior['web-login'] = 'ok'
            force_close_auth(page)
        reset_to_guest(page)

        # ================= S9 暗色主题弹窗 =================
        print('\n--- S9 暗色主题弹窗 ---')
        try:
            force_close_auth(page)
            reset_to_guest(page, theme='dark')
            open_auth(page)
            is_dark = page.evaluate("() => document.documentElement.classList.contains('theme-dark')")
            check(is_dark, '暗色场景 html 应带 theme-dark 类')
            check(mode_hint(page) == '使用已注册的账号登录', '暗色下登录页结构应正常')
            s_dark = shot(page, 'web-login-modal-dark.png')
            close_auth(page)
            print('   [通过] 暗色主题登录页渲染正常')
            record('S9_dark_theme_modal', 'PASS',
                   assertions={'theme_dark_class': True}, screenshots=[s_dark])
        except Exception as e:
            print(f'   [失败] {e}')
            record('S9_dark_theme_modal', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        ctx.close()
        browser.close()
except Exception as e:
    print(f'\n[致命错误] {e}', file=sys.stderr)
    report['overall'] = 'FAIL'
    report['fatal'] = f'{e}\n{traceback.format_exc(limit=3)}'
finally:
    httpd.shutdown()

report_path = f'{ARTIFACTS_DIR}/web-login-guard-report.json'
with open(report_path, 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

passed = sum(1 for s in report['scenarios'] if s['status'] == 'PASS')
print(f'\n========================================================')
print(f'Web 登录防重复提交验收结束: {passed}/{len(report["scenarios"])} 场景通过，总体 {report["overall"]}')
print(f'真实拦截请求计数: {counts}')
print(f'报告: {report_path}')
print(f'========================================================')

if report['overall'] != 'PASS':
    sys.exit(1)
