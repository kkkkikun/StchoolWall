#!/usr/bin/env python3
"""
SchoolWall 学生端 H5 发布页图片上传真实浏览器验收
（独立脚本；复用 h5_mock_api.py 共享 Mock；单 Chromium 390x844 串行）

真实调用链：页面「添加照片」→ 生产 uni.chooseImage（Playwright file chooser 拦截
注入合成图片，无系统对话框）→ 生产 uploadOne/uploadMedia/uni.uploadFile（真实 XHR
multipart POST /api/v1/upload/direct?kind=posts，Playwright 路由拦截控制挂起/失败/成功）
→ 生产 onSubmit → POST /posts（拦截计数并捕获请求体）。

场景：
  U1 上传在途：图片显示上传中遮罩；点发布零 POST 且提示「图片还在上传中」；放行后进入完成态
  U2 上传失败：进入失败态、重试入口可见；toast 为「网络连接失败，请检查网络后重试」，
     不暴露底层 errMsg；失败图片存在时点发布零 POST 且提示先处理失败图片
  U3 重试成功 + 发布：经页面重试入口二次上传成功，失败态解除；发布请求体 media_ids
     包含全部已上传 media_id

产物：ci-artifacts/ui-walkthrough/publish-upload-report.json + publish-upload-*.png
任一断言失败 -> 场景 FAIL，脚本退出码非零。全部为 Mock API，不代表真实后端联调。
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
from playwright.sync_api import sync_playwright

from h5_mock_api import handle_api, assert_no_horizontal_overflow

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIST_DIR = os.path.join(ROOT_DIR, 'frontend', 'dist', 'build', 'h5')
ARTIFACTS_DIR = os.path.join(ROOT_DIR, 'ci-artifacts', 'ui-walkthrough')
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

if not os.path.isdir(DIST_DIR):
    print(f"Error: DIST_DIR not found at {DIST_DIR}. Run 'npm run build:h5' first.", file=sys.stderr)
    sys.exit(1)

# 1x1 红色 PNG（合法文件头，供 file chooser 注入）
PNG_BYTES = bytes.fromhex(
    '89504e470d0a1a0a0000000d494844520000000100000001080600000'
    '01f15c4890000000d49444154789c626001000000ffff030000060005'
    '57bfabd40000000049454e44ae426082'
)

SESSION_OK = {
    'code': 0, 'message': 'success',
    'data': {
        'access_token': 'mock-access-token-for-upload-test',
        'csrf_token': 'mock-csrf-token',
        'session_id': 'mock-session-id',
        'role': 'guest',
        'user_info': {'id': 'u-upload-test', 'nickname': '上传测试同学', 'is_verified': False},
    },
}

# ---------------------------------------------------------------- 静态服务
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind(('127.0.0.1', 0))
port = sock.getsockname()[1]
sock.close()

class SilentHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST_DIR, **kwargs)
    def log_message(self, format, *args):
        pass

socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(('127.0.0.1', port), SilentHandler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
base_url = f'http://127.0.0.1:{port}'
print(f'H5 static server listening on {base_url}')

# ---------------------------------------------------------------- Mock 状态
upload_calls = {'count': 0}
held_uploads = []
upload_behavior = {'mode': 'ok'}  # ok | hold | abort
media_seq = {'n': 0}
issued_media_ids = []  # 按签发顺序记录全部成功上传的 media_id（供边界场景精确对账）

post_calls = {'count': 0, 'bodies': []}


def media_body():
    media_seq['n'] += 1
    mid = f'm-media-{media_seq["n"]:03d}'
    issued_media_ids.append(mid)
    return {'code': 0, 'data': {'media_id': mid, 'status': 'quarantine', 'public_url': None}}, mid

def handle_upload(route):
    if route.request.method != 'POST':
        return handle_api(route)
    upload_calls['count'] += 1
    mode = upload_behavior['mode']
    if mode == 'hold':
        held_uploads.append(route)
        return
    if mode == 'abort':
        route.abort()
        return
    body, _ = media_body()
    route.fulfill(status=200, content_type='application/json', body=json.dumps(body))

def release_uploads():
    routes = held_uploads[:]
    held_uploads.clear()
    ids = []
    for r in routes:
        try:
            body, mid = media_body()
            r.fulfill(status=200, content_type='application/json', body=json.dumps(body))
            ids.append(mid)
        except Exception:
            pass
    return ids

def handle_posts(route):
    if route.request.method != 'POST':
        return handle_api(route)
    post_calls['count'] += 1
    try:
        post_calls['bodies'].append(json.loads(route.request.post_data or '{}'))
    except Exception:
        post_calls['bodies'].append(None)
    route.fulfill(status=200, content_type='application/json',
                  body=json.dumps({'code': 0, 'data': {'post_id': 9101, 'status': 0}}))

def handle_web_login(route):
    route.fulfill(status=200, content_type='application/json', body=json.dumps(SESSION_OK))

def handle_profile(route):
    route.fulfill(status=200, content_type='application/json', body=json.dumps({
        'code': 0, 'data': {'nickname': '上传测试同学', 'is_verified': False}}))

# ---------------------------------------------------------------- 工具
class ScenarioFailure(Exception):
    pass

def check(cond, msg):
    if not cond:
        raise ScenarioFailure(msg)

report = {
    'task': 'student H5 publish page image upload acceptance',
    'date_utc': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
    'base_url': base_url,
    'browser': 'chromium(headless)',
    'viewport': '390x844',
    'mock_scope': ('Production uni.chooseImage driven via Playwright file-chooser interception '
                   '(synthetic PNG, no OS dialog); real XHR uploads to /api/v1/upload/direct '
                   'intercepted (hold/abort/ok); login via real UI + mocked web-login. No real backend.'),
    'upload_requests': upload_calls,
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
    page.evaluate('''(v) => {
        const t = document.querySelector('.post-textarea textarea') ||
                  document.querySelector('.post-textarea');
        t.value = v;
        t.dispatchEvent(new Event('input', { bubbles: true }));
    }''', text)
    page.wait_for_timeout(150)

def choose_image(page, name='campus.png'):
    """点击「添加照片」，拦截真实 file chooser 并注入合成 PNG（不开系统对话框）。"""
    with page.expect_file_chooser(timeout=5000) as fc_info:
        page.locator('.upload-box').click()
    fc_info.value.set_files({'name': name, 'mimeType': 'image/png', 'buffer': PNG_BYTES})
    page.wait_for_timeout(300)

def choose_images_multi(page, names, expect_multiple=None):
    """一次选择多张：set_files 注入多个合成 PNG，完整经过生产 chooseImage 回调。
    expect_multiple 不为 None 时断言选择器 multiple 属性（count>1 → multiple，count=1 → 单文件）。"""
    with page.expect_file_chooser(timeout=5000) as fc_info:
        page.locator('.upload-box').click()
    fc = fc_info.value
    if expect_multiple is not None:
        check(fc.is_multiple() == expect_multiple,
              f'文件选择器 multiple 应为 {expect_multiple}，实际 {fc.is_multiple()}')
    fc.set_files([{'name': n, 'mimeType': 'image/png', 'buffer': PNG_BYTES} for n in names])
    page.wait_for_timeout(400)

def login_via_ui(page):
    page.goto(f'{base_url}/#/pages/mine/index')
    page.wait_for_selector('.dev-login-row', timeout=8000)
    page.locator('.dev-capsule:has-text("登录 / 注册")').click()
    page.wait_for_selector('.auth-form', timeout=5000)
    page.evaluate('''() => {
        const inputs = document.querySelectorAll('.auth-form .auth-input input');
        ['upload_tester', 'password123'].forEach((v, i) => {
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

def goto_publish_via_tab(page):
    page.locator('.tab-bar .tab-item').nth(2).click()
    page.wait_for_selector('.publish-btn', timeout=8000)
    page.wait_for_timeout(500)

exit_code = 0
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={'width': 390, 'height': 844})
        page = ctx.new_page()
        page.route('**/api/v1/**', handle_api)  # 兜底先注册（Playwright 后注册优先）
        page.route('**/api/v1/upload/**', handle_upload)
        page.route('**/api/v1/posts', handle_posts)
        page.route('**/api/v1/auth/web-login', handle_web_login)
        page.route('**/api/v1/user/profile', handle_profile)

        login_via_ui(page)
        goto_publish_via_tab(page)
        set_content(page, '出闲置宿舍台灯，九成新，带原装充电线')

        # ================= U1 上传在途 =================
        print('\n--- U1 上传在途：遮罩 + 发布拦截 + 放行完成 ---')
        try:
            upload_behavior['mode'] = 'hold'
            choose_image(page)
            page.wait_for_timeout(400)
            check(page.locator('.img-cell').count() == 1, '应出现 1 个图片格子')
            check(page.locator('.img-mask').first.is_visible(), '上传中遮罩应可见')
            check(upload_calls['count'] == 1, f'应有 1 次上传请求，实际 {upload_calls["count"]}')
            s1 = shot(page, 'publish-upload-inflight.png')

            before_posts = post_calls['count']
            page.locator('.publish-btn').click()
            page.wait_for_timeout(600)
            check(post_calls['count'] == before_posts,
                  f'上传在途时点发布不得发出 POST /posts（{before_posts} -> {post_calls["count"]}）')
            t = toast_text(page)
            check('上传中' in t, f'应提示图片仍在上传，实际 toast: 「{t}」')

            ids = release_uploads()
            page.wait_for_timeout(800)
            check(page.locator('.img-mask').count() == 0, '放行后遮罩应消失（进入完成态）')
            check(page.locator('.img-cell').count() == 1, '图片格子应保留')
            print(f'   [通过] 在途遮罩/发布拦截正常，放行后完成（media_id={ids}）')
            record('U1_upload_inflight', 'PASS',
                   assertions={'upload_requests': 1, 'post_delta_inflight': 0,
                               'toast': t, 'released_media_ids': ids}, screenshots=[s1])
        except Exception as e:
            print(f'   [失败] {e}')
            record('U1_upload_inflight', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            release_uploads()
            upload_behavior['mode'] = 'ok'

        # ================= U2 上传失败 =================
        print('\n--- U2 上传失败：失败态 + 友好提示 + 发布拦截 ---')
        try:
            upload_behavior['mode'] = 'abort'
            choose_image(page, name='desk.png')
            page.wait_for_timeout(1000)
            check(page.locator('.img-cell').count() == 2, '应有 2 个图片格子')
            failed = page.locator('.img-mask.failed')
            check(failed.count() == 1, f'应有 1 个失败遮罩，实际 {failed.count()}')
            check(failed.first.is_visible(), '失败遮罩（重试入口）应可见')
            check('重试' in failed.first.inner_text(), '失败遮罩应含「重试」文案')
            t = toast_text(page)
            check('网络连接失败，请检查网络后重试' in t,
                  f'失败 toast 应含友好网络提示，实际: 「{t}」')
            check('request:fail' not in t and 'uploadFile' not in t,
                  f'不得暴露底层错误原文，实际: 「{t}」')
            s2 = shot(page, 'publish-upload-failed.png')

            before_posts = post_calls['count']
            page.locator('.publish-btn').click()
            page.wait_for_timeout(600)
            check(post_calls['count'] == before_posts,
                  f'失败图片存在时点发布不得发出 POST（{before_posts} -> {post_calls["count"]}）')
            t2 = toast_text(page)
            check('重试或删除' in t2, f'应提示先处理失败图片，实际 toast: 「{t2}」')
            print(f'   [通过] 失败态+重试入口+友好提示正常，发布被拦截（toast=「{t2}」）')
            record('U2_upload_failed', 'PASS',
                   assertions={'failed_mask': True, 'retry_entry': True,
                               'toast': t, 'post_delta': 0, 'block_toast': t2}, screenshots=[s2])
        except Exception as e:
            print(f'   [失败] {e}')
            record('U2_upload_failed', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            upload_behavior['mode'] = 'ok'

        # ================= U3 重试成功 + 发布请求体 =================
        print('\n--- U3 重试成功 + 发布请求体含 media_id ---')
        try:
            upload_behavior['mode'] = 'ok'
            before_uploads = upload_calls['count']
            page.locator('.img-mask.failed').first.click()
            page.wait_for_timeout(1000)
            check(upload_calls['count'] - before_uploads == 1,
                  f'重试应发起第 2 次上传，实际增量 {upload_calls["count"] - before_uploads}')
            check(page.locator('.img-mask.failed').count() == 0, '重试成功后失败态应解除')
            s3 = shot(page, 'publish-upload-ready.png')

            before_posts = post_calls['count']
            page.locator('.publish-btn').click()
            page.wait_for_timeout(2000)
            check(post_calls['count'] - before_posts == 1, '发布应恰好 1 次 POST /posts')
            body = post_calls['bodies'][-1]
            media_ids = (body or {}).get('media_ids') or []
            check(len(media_ids) == 2, f'请求体应含 2 个 media_id，实际: {media_ids}')
            check(all(str(m).startswith('m-media-') for m in media_ids),
                  f'media_id 应来自上传响应，实际: {media_ids}')
            page.wait_for_selector('.feed-card', timeout=8000)
            check(page.locator('.publish-btn').count() == 0, '成功后应离开发布页')
            print(f'   [通过] 重试 1 次成功，发布请求体 media_ids={media_ids}')
            record('U3_retry_and_publish', 'PASS',
                   assertions={'retry_uploads_delta': 1, 'post_delta': 1,
                               'media_ids': media_ids, 'left_publish_page': True}, screenshots=[s3])
        except Exception as e:
            print(f'   [失败] {e}')
            record('U3_retry_and_publish', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= U4 连续添加至上限 6 张 =================
        print('\n--- U4 连续添加 6 张至上限 ---')
        try:
            goto_publish_via_tab(page)
            set_content(page, '毕业季清仓：台灯、书架、收纳箱、衣架一起出')
            upload_behavior['mode'] = 'ok'
            before_uploads = upload_calls['count']
            for i in range(6):
                choose_image(page, name=f'item-{i+1}.png')
                page.wait_for_timeout(400)
            check(upload_calls['count'] - before_uploads == 6,
                  f'6 张图片应对应 6 次真实上传请求，实际增量 {upload_calls["count"] - before_uploads}')
            check(page.locator('.img-cell').count() == 6, '应渲染 6 个图片格子')
            check(page.locator('.img-mask').count() == 0, '全部图片应进入完成态（无遮罩）')
            s4 = shot(page, 'publish-upload-limit-6.png')
            print(f'   [通过] 6 张全部走真实上传链路上传成功')
            record('U4_add_to_max_6', 'PASS',
                   assertions={'upload_delta': 6, 'cells': 6, 'masks': 0}, screenshots=[s4])
        except Exception as e:
            print(f'   [失败] {e}')
            record('U4_add_to_max_6', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= U5 达到上限后入口隐藏 =================
        print('\n--- U5 达上限后第 7 张入口隐藏、零额外上传 ---')
        try:
            check(page.locator('.upload-box').count() == 0 or not page.locator('.upload-box').is_visible(),
                  '满 6 张后「添加照片」入口应隐藏（v-if）')
            before_uploads = upload_calls['count']
            page.wait_for_timeout(500)
            check(upload_calls['count'] == before_uploads, '不得产生第 7 次上传请求')
            check(page.locator('.img-cell').count() == 6, '图片数应仍为 6')
            print('   [通过] 上限入口隐藏，无第 7 张、无额外上传')
            record('U5_overflow_blocked', 'PASS',
                   assertions={'upload_box_hidden': True, 'extra_uploads': 0, 'cells': 6})
        except Exception as e:
            print(f'   [失败] {e}')
            record('U5_overflow_blocked', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= U6 删除 1 张 + 补传 1 张 + 发布对账 =================
        print('\n--- U6 删除/补传/发布 media_ids 对账 ---')
        try:
            deleted_mid = issued_media_ids[2]  # U4 批次第一张（格子顺序与上传顺序一致）
            page.locator('.img-cell').first.locator('.img-del').click()
            page.wait_for_timeout(400)
            check(page.locator('.img-cell').count() == 5, '删除后应为 5 张')
            check(page.locator('.upload-box').is_visible(), '删除后上传入口应恢复可见')
            check(page.locator('.upload-count').inner_text().strip() == '5/6', '计数应为 5/6')

            before_uploads = upload_calls['count']
            choose_image(page, name='replacement.png')
            page.wait_for_timeout(500)
            check(upload_calls['count'] - before_uploads == 1, '补传应恰好 1 次上传请求')
            check(page.locator('.img-cell').count() == 6, '补传后恢复 6 张')
            check(page.locator('.upload-box').count() == 0 or not page.locator('.upload-box').is_visible(),
                  '补满 6 张后入口应再次隐藏')
            s6 = shot(page, 'publish-upload-final.png')

            before_posts = post_calls['count']
            page.locator('.publish-btn').click()
            page.wait_for_timeout(2000)
            check(post_calls['count'] - before_posts == 1, '发布应恰好 1 次 POST')
            body = post_calls['bodies'][-1]
            media_ids = (body or {}).get('media_ids') or []
            expected = issued_media_ids[3:]  # 去掉 U1/U3 的两张与被删除的第一张
            check(media_ids == expected,
                  f'发布 media_ids 应与页面保留图片一一对应且不含已删除项。\n'
                  f'  期望: {expected}\n  实际: {media_ids}\n  已删除: {deleted_mid}')
            check(deleted_mid not in media_ids, f'已删除的 {deleted_mid} 不得出现在发布请求体')
            page.wait_for_selector('.feed-card', timeout=8000)
            print(f'   [通过] 删除→补传→发布对账一致，media_ids={media_ids}')
            record('U6_delete_readd_publish', 'PASS',
                   assertions={'deleted_media_id': deleted_mid, 'final_media_ids': media_ids,
                               'matches_remaining_images': True}, screenshots=[s6])
        except Exception as e:
            print(f'   [失败] {e}')
            record('U6_delete_readd_publish', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= U7 一次多选 4 张 =================
        print('\n--- U7 空白页一次选择 4 张 ---')
        try:
            goto_publish_via_tab(page)
            set_content(page, '宿舍好物合集转卖，看图挑选，打包优惠')
            base_issued = len(issued_media_ids)
            before_uploads = upload_calls['count']
            choose_images_multi(page, ['m1.png', 'm2.png', 'm3.png', 'm4.png'], expect_multiple=True)
            page.wait_for_timeout(1500)
            check(page.locator('.img-cell').count() == 4, '应渲染 4 个图片格子')
            check(upload_calls['count'] - before_uploads == 4,
                  f'4 张应对应 4 次上传请求，实际增量 {upload_calls["count"] - before_uploads}')
            new_ids = issued_media_ids[base_issued:]
            check(len(new_ids) == 4 and len(set(new_ids)) == 4, f'应签发 4 个唯一 media_id，实际 {new_ids}')
            check(page.locator('.img-mask').count() == 0, '4 张全部应进入完成态')
            s7 = shot(page, 'publish-upload-multi-4.png')
            print(f'   [通过] 一次多选 4 张：4 格 / 4 次上传 / 唯一 media_id {new_ids}')
            record('U7_multi_select_4', 'PASS',
                   assertions={'cells': 4, 'upload_delta': 4, 'unique_media_ids': new_ids,
                               'all_done': True}, screenshots=[s7])
        except Exception as e:
            print(f'   [失败] {e}')
            record('U7_multi_select_4', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= U8 剩余 2 张时多选 4 张（双重上限保护） =================
        print('\n--- U8 剩余 2 张时注入 4 张：uni 按 count 截断 + 页面 MAX 保护 ---')
        try:
            before_uploads = upload_calls['count']
            choose_images_multi(page, ['x1.png', 'x2.png', 'x3.png', 'x4.png'], expect_multiple=True)
            page.wait_for_timeout(1500)
            check(page.locator('.img-cell').count() == 6,
                  f'图片数不得超过 6，实际 {page.locator(".img-cell").count()}')
            check(upload_calls['count'] - before_uploads == 2,
                  f'仅应为被接受的 2 张发起上传，实际增量 {upload_calls["count"] - before_uploads}')
            check(page.locator('.img-mask').count() == 0, '被接受的图片应完成上传')
            check(page.locator('.upload-box').count() == 0 or not page.locator('.upload-box').is_visible(),
                  '满 6 张后上传入口应隐藏')
            print('   [通过] 注入 4 张仅接受 2 张、仅 2 次上传，上限保护生效')
            record('U8_multi_overflow_clamped', 'PASS',
                   assertions={'injected': 4, 'accepted_cells': 6, 'upload_delta': 2})
        except Exception as e:
            print(f'   [失败] {e}')
            record('U8_multi_overflow_clamped', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= U9 剩余 1 张时选择器单文件契约 =================
        print('\n--- U9 剩余 1 张：count=1 → 单文件选择器 ---')
        try:
            page.locator('.img-cell').first.locator('.img-del').click()
            page.wait_for_timeout(400)
            check(page.locator('.img-cell').count() == 5, '删除后应为 5 张')
            before_uploads = upload_calls['count']
            # count=1 时 uni-h5 不设置 multiple（uni-h5.es.js _createInput: count>1 才 multiple）；
            # Playwright/浏览器禁止向单文件 input 注入多文件，超量注入路径在平台层即被阻断，
            # 因此本场景验证选择器契约 + 单张补传，不伪称覆盖「单文件选择器注入多文件」。
            choose_images_multi(page, ['last.png'], expect_multiple=False)
            page.wait_for_timeout(1200)
            check(upload_calls['count'] - before_uploads == 1, '补传应恰好 1 次上传')
            check(page.locator('.img-cell').count() == 6, '补传后恢复 6 张')
            check(page.locator('.img-mask').count() == 0, '补传图片应完成')
            print('   [通过] count=1 时选择器为单文件（multiple=False），补传 1 张成功')
            record('U9_remain_one_single_chooser', 'PASS',
                   assertions={'chooser_multiple': False, 'upload_delta': 1, 'cells': 6,
                               'note': '浏览器禁止向单文件 input 注入多文件，超量路径平台层阻断'})
        except Exception as e:
            print(f'   [失败] {e}')
            record('U9_remain_one_single_chooser', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        # ================= U10 多选流程最终发布对账 =================
        print('\n--- U10 多选流程发布 media_ids 终态对账 ---')
        try:
            s10 = shot(page, 'publish-upload-multi-final.png')
            # 先记录页面格子顺序（发布成功后会离开发布页），再发起发布
            # 并发上传时「签发顺序」≠「用户选择顺序」，以页面格子顺序为准对账：
            # 发布请求的 media_ids 必须与用户看到的图片顺序一一对应。
            cell_ids = page.eval_on_selector_all(
                '.img-cell', 'els => els.map(el => el.getAttribute("data-media-id") || "")')
            check(all(cell_ids), f'格子应带 data-media-id，实际: {cell_ids}')
            check(len(cell_ids) == 6, f'应有 6 个格子，实际 {len(cell_ids)}')
            before_posts = post_calls['count']
            page.locator('.publish-btn').click()
            page.wait_for_timeout(2000)
            check(post_calls['count'] - before_posts == 1, '发布应恰好 1 次 POST')
            body = post_calls['bodies'][-1]
            media_ids = (body or {}).get('media_ids') or []
            check(media_ids == cell_ids,
                  f'最终 media_ids 顺序应与页面格子顺序一致。\n期望(格子顺序): {cell_ids}\n实际: {media_ids}')
            check(len(set(media_ids)) == len(media_ids), f'media_ids 不应重复: {media_ids}')
            page.wait_for_selector('.feed-card', timeout=8000)
            print(f'   [通过] 终态对账一致，media_ids={media_ids}')
            record('U10_multi_publish_reconcile', 'PASS',
                   assertions={'final_media_ids': media_ids, 'matches_remaining': True,
                               'grid_order': cell_ids},
                   screenshots=[s10])
        except Exception as e:
            print(f'   [失败] {e}')
            record('U10_multi_publish_reconcile', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

        ctx.close()
        browser.close()
except Exception as e:
    print(f'\n[致命错误] {e}', file=sys.stderr)
    report['overall'] = 'FAIL'
    report['fatal'] = f'{e}\n{traceback.format_exc(limit=3)}'
finally:
    httpd.shutdown()

report_path = f'{ARTIFACTS_DIR}/publish-upload-report.json'
with open(report_path, 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

passed = sum(1 for s in report['scenarios'] if s['status'] == 'PASS')
print(f'\n========================================================')
print(f'图片上传验收结束: {passed}/{len(report["scenarios"])} 场景通过，总体 {report["overall"]}')
print(f'上传请求计数: {upload_calls["count"]}, POST /posts 计数: {post_calls["count"]}')
print(f'报告: {report_path}')
print(f'========================================================')

if report['overall'] != 'PASS':
    sys.exit(1)
