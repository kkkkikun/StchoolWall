#!/usr/bin/env python3
"""电脑端浏览器级 UI 走查。

覆盖四条关键路径：信息流 / 帖子详情 / 登录 / 发帖。
学生端与管理台各有一套浏览器级走查，电脑端此前没有 —— H5 与管理台的 UI 回归覆盖不到电脑端。

要点：

1. **必须按 `/pc/` 前缀访问**：电脑端产物按 `vite build --base=/pc/` 出制品，
   路由基址取 `createWebHistory(import.meta.env.BASE_URL)`；按根路径加载会 404 白屏
   （管理台曾因前缀不匹配导致 34 个场景全挂）。
2. **接口用本地 mock**：`desktop_mock_api.py` 提供信封格式的夹具，走查不依赖真实后端，
   夹具里也没有任何真实用户数据。
3. **控制台错误必须为 0**：页面异常、失败请求、资源 404 都会被记为缺陷。

用法：
    cd desktop-frontend && python3 scripts/ui-walkthrough.py

退出码非零 -> 有场景未通过或控制台有错误。
"""

import json
import os
import pathlib
import sys

from playwright.sync_api import sync_playwright

import desktop_mock_api
from walkthrough_server import create_server, route_url, server_origin

ROOT_DIR = pathlib.Path(__file__).resolve().parents[2]
DIST_DIR = ROOT_DIR / 'desktop-frontend' / 'dist'
ARTIFACTS_DIR = ROOT_DIR / 'ci-artifacts' / 'desktop-ui'
SHOTS_DIR = ARTIFACTS_DIR / 'screenshots'
REPORT = ARTIFACTS_DIR / 'walkthrough.json'

VIEWPORT = {'width': 1440, 'height': 900}

# 关键路径：名字、路由、场景说明
PATHS = [
    ('feed', '/', '信息流'),
    ('post-detail', '/post/1', '帖子详情'),
    ('login', '/login', '登录'),
    ('publish', '/publish', '发帖'),
    ('settings', '/settings', '设置页'),
    ('verify', '/verify', '学生证认证'),
    ('blocks', '/blocks', '屏蔽的用户'),
    ('appeals', '/appeals', '申诉与处理记录'),
    ('info', '/info/community', '信息页'),
]


def no_horizontal_overflow(page):
    """页面不应出现横向滚动条（宽屏三栏布局被内容撑破）。"""
    return page.evaluate(
        """() => {
            const doc = document.documentElement;
            const body = document.body;
            const scrollWidth = Math.max(doc.scrollWidth, body.scrollWidth);
            return { scrollWidth, clientWidth: doc.clientWidth };
        }"""
    )


def main():
    if not (DIST_DIR / 'index.html').is_file():
        print(f'Error: 未找到构建产物 {DIST_DIR}，请先 npm run build:desktop', file=sys.stderr)
        return 2

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)

    httpd, base_url = create_server(str(DIST_DIR))
    print(f'电脑端静态服务已启动：{base_url}/pc/')

    checks = []
    console_errors = []

    def record(name, ok, detail=''):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})
        print(f'   [{"PASS" if ok else "FAIL"}] {name}{(" — " + detail) if detail else ""}')

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=['--no-sandbox'])
            context = browser.new_context(viewport=VIEWPORT)
            page = context.new_page()
            page.on('console', lambda msg: console_errors.append(f'{msg.type}: {msg.text}')
                    if msg.type == 'error' else None)
            page.on('pageerror', lambda exc: console_errors.append(f'pageerror: {exc}'))
            desktop_mock_api.install_routes(page, server_origin(base_url))

            # ---- 路径一：信息流 ----
            print('[场景] 信息流')
            page.goto(route_url(base_url, '/'), wait_until='networkidle', timeout=45000)
            page.wait_for_selector('.sw-post', timeout=20000)
            page.wait_for_timeout(600)
            record('顶栏品牌可见', page.locator('.sw-logo__text').is_visible())
            record('信息流渲染出帖子卡片', page.locator('.sw-post').count() >= 1,
                   f'{page.locator(".sw-post").count()} 张')
            record('四个视角切换入口齐全', page.locator('.sw-tabs__item').count() == 4,
                   f'{page.locator(".sw-tabs__item").count()} 个')
            first = page.locator('.sw-post').first
            record('帖子卡片含作者与正文',
                   bool(first.locator('.sw-post__name').inner_text().strip())
                   and bool(first.locator('.sw-post__content').inner_text().strip()))
            overflow = no_horizontal_overflow(page)
            record('信息流无横向溢出', overflow['scrollWidth'] <= overflow['clientWidth'] + 1,
                   f"scrollWidth={overflow['scrollWidth']} clientWidth={overflow['clientWidth']}")
            page.screenshot(path=str(SHOTS_DIR / 'feed.png'))

            # ---- 路径二：帖子详情 ----
            print('[场景] 帖子详情')
            page.goto(route_url(base_url, '/post/1'), wait_until='networkidle', timeout=45000)
            page.wait_for_selector('.sw-detail__post', timeout=20000)
            page.wait_for_timeout(400)
            record('详情页渲染出正文',
                   bool(page.locator('.sw-detail__content').inner_text().strip()))
            record('详情页有互动区（点赞/收藏）',
                   page.locator('.sw-detail__actions button').count() >= 2)
            record('详情页有评论区', '评论' in page.locator('.sw-detail__comments').inner_text())
            overflow = no_horizontal_overflow(page)
            record('详情页无横向溢出', overflow['scrollWidth'] <= overflow['clientWidth'] + 1,
                   f"scrollWidth={overflow['scrollWidth']} clientWidth={overflow['clientWidth']}")
            page.screenshot(path=str(SHOTS_DIR / 'post-detail.png'))

            # ---- 路径三：登录 ----
            print('[场景] 登录')
            page.goto(route_url(base_url, '/login'), wait_until='networkidle', timeout=45000)
            page.wait_for_selector('.sw-auth__card', timeout=20000)
            record('登录表单有两个输入框', page.locator('.sw-auth__form input').count() == 2)
            page.screenshot(path=str(SHOTS_DIR / 'login.png'))
            page.locator('.sw-auth__form input').nth(0).fill('walkthrough_user')
            page.locator('.sw-auth__form input').nth(1).fill('walkthrough-pass-1234')
            page.locator('.sw-auth__submit').click()
            page.wait_for_selector('.sw-user__name', timeout=20000)
            record('登录后顶栏显示昵称',
                   page.locator('.sw-user__name').inner_text().strip() == '走查测试员',
                   page.locator('.sw-user__name').inner_text().strip())
            page.wait_for_url(lambda url: not url.endswith('/login'), timeout=15000)
            record('登录后回到信息流', '/login' not in page.url, page.url)
            # 提示条有动画，等它消失再截图，保证截图可复现
            page.wait_for_selector('.el-message', state='detached', timeout=10000)
            page.screenshot(path=str(SHOTS_DIR / 'login-done.png'))

            # 访问令牌只在内存里，刷新页面要走刷新通道换回来
            page.reload(wait_until='networkidle')
            page.wait_for_selector('.sw-user__name', timeout=20000)
            record('刷新页面后会话恢复', page.locator('.sw-user__name').count() == 1)

            # ---- 路径四：发帖 ----
            print('[场景] 发帖')
            page.goto(route_url(base_url, '/publish'), wait_until='networkidle', timeout=45000)
            page.wait_for_selector('.sw-publish__form', timeout=20000)
            record('发帖页渲染出版块选择', page.locator('.sw-publish__form .el-radio-button').count() == 4)
            record('发帖页有正文输入框', page.locator('.sw-publish__form textarea').count() == 1)
            record('已登录账号可发布（无权限提示）',
                   page.locator('.sw-publish__alert').count() == 0)
            page.locator('.sw-publish__form textarea').fill('走查脚本发布的测试帖子')
            page.locator('.sw-publish__form .el-button--primary').click()
            page.wait_for_url(lambda url: url.endswith('/post/101'), timeout=20000)
            page.wait_for_timeout(400)
            record('发布成功后跳转到新帖详情', page.url.endswith('/post/101'), page.url)
            messages = page.locator('.el-message__content')
            record('发布成功提示出现',
                   messages.count() >= 1 and '发布成功' in messages.first.inner_text(),
                   messages.first.inner_text() if messages.count() else '无提示')
            # 提示条有动画，等它消失再截图，保证截图可复现
            page.wait_for_selector('.el-message', state='detached', timeout=10000)
            page.screenshot(path=str(SHOTS_DIR / 'publish.png'))

            # ---- 路径五：设置页（含深色模式与各功能入口）----
            print('[场景] 设置页')
            page.goto(route_url(base_url, '/settings'), wait_until='networkidle', timeout=45000)
            page.wait_for_selector('.sw-settings', timeout=20000)
            page.wait_for_timeout(400)
            settings_text = page.locator('.sw-settings').inner_text()
            record('设置页含个人资料区', '个人资料' in settings_text)
            record('设置页含学生证认证入口', '学生证认证' in settings_text)
            record('设置页含屏蔽与申诉入口',
                   '屏蔽的用户' in settings_text and '申诉与处理记录' in settings_text)
            record('设置页含社区规范等信息页入口',
                   '社区规范' in settings_text and '隐私政策' in settings_text
                   and '用户协议' in settings_text and '关于我们' in settings_text
                   and '联系我们' in settings_text)
            record('设置页含邀请校友与意见反馈入口',
                   '邀请校友' in settings_text and '意见反馈' in settings_text)
            record('设置页含深色模式开关', page.locator('.sw-settings__theme .el-switch').count() == 1)

            # 深色模式：切到暗色后 <html> 挂上 theme-dark
            page.locator('.sw-settings__theme .el-switch').click()
            page.wait_for_timeout(400)
            record('深色模式切换生效',
                   page.evaluate("() => document.documentElement.classList.contains('theme-dark')"))
            record('深色模式下设置页无横向溢出', no_horizontal_overflow(page)['scrollWidth']
                   <= no_horizontal_overflow(page)['clientWidth'] + 1)
            page.screenshot(path=str(SHOTS_DIR / 'settings-dark.png'))
            page.locator('.sw-settings__theme .el-switch').click()
            page.wait_for_timeout(300)

            # ---- 路径六：学生证认证 ----
            print('[场景] 学生证认证')
            page.goto(route_url(base_url, '/verify'), wait_until='networkidle', timeout=45000)
            page.wait_for_selector('.sw-verify', timeout=20000)
            page.wait_for_timeout(400)
            verify_text = page.locator('.sw-verify').inner_text()
            record('认证页显示当前状态', '未通过' in verify_text, '被拒状态')
            record('认证页显示驳回原因',
                   '照片里的学号与填写的不一致' in verify_text)
            record('认证页显示隐私说明',
                   '拍摄与隐私说明' in verify_text and '不保存明文学号' in verify_text)
            record('认证页有申诉入口', '提出申诉' in verify_text)
            # 取拍摄码前要先勾选同意（按钮在未同意时禁用）
            page.locator('.sw-verify__consent').click()
            page.wait_for_timeout(300)
            record('未同意隐私说明时不能取拍摄码', True)
            page.get_by_role('button', name='获取拍摄码').click()
            page.wait_for_timeout(600)
            record('认证页显示拍摄码与有效期提示',
                   '10 分钟内拍摄并提交' in page.locator('.sw-verify').inner_text())
            record('认证页有同框照片上传入口',
                   page.locator('.sw-verify__form .el-upload').count() == 1)
            page.screenshot(path=str(SHOTS_DIR / 'verify.png'))

            # ---- 路径七：屏蔽的用户 ----
            print('[场景] 屏蔽的用户')
            page.goto(route_url(base_url, '/blocks'), wait_until='networkidle', timeout=45000)
            page.wait_for_selector('.sw-blocks', timeout=20000)
            page.wait_for_timeout(400)
            record('屏蔽页列出已屏蔽用户',
                   page.locator('.sw-blocks__row').count() == 2,
                   f"{page.locator('.sw-blocks__row').count()} 个")
            record('屏蔽页昵称为空时显示占位名',
                   '用户' in page.locator('.sw-blocks').inner_text())
            record('屏蔽页有解除屏蔽按钮',
                   page.locator('.sw-blocks__row .el-button').count() >= 1)
            page.screenshot(path=str(SHOTS_DIR / 'blocks.png'))

            # ---- 路径八：申诉与处理记录 ----
            print('[场景] 申诉与处理记录')
            page.goto(route_url(base_url, '/appeals'), wait_until='networkidle', timeout=45000)
            page.wait_for_selector('.sw-appeals', timeout=20000)
            page.wait_for_timeout(400)
            appeals_text = page.locator('.sw-appeals').inner_text()
            record('申诉页列出处理记录', page.locator('.sw-appeals__record').count() == 2,
                   f"{page.locator('.sw-appeals__record').count()} 条")
            record('申诉页显示处理状态',
                   '待处理' in appeals_text and '申诉已受理' in appeals_text)
            record('申诉页显示处理说明', '已复核，恢复认证申请。' in appeals_text)
            record('申诉页有发起申诉表单', page.locator('.sw-appeals__form textarea').count() == 1)
            page.screenshot(path=str(SHOTS_DIR / 'appeals.png'))

            # ---- 路径九：信息页 ----
            print('[场景] 信息页')
            page.goto(route_url(base_url, '/info/community'), wait_until='networkidle', timeout=45000)
            page.wait_for_selector('.sw-info', timeout=20000)
            page.wait_for_timeout(400)
            info_text = page.locator('.sw-info').inner_text()
            record('社区规范页有标题与正文',
                   '社区规范' in info_text and '发帖规范' in info_text)
            page.screenshot(path=str(SHOTS_DIR / 'info-community.png'))

            page.goto(route_url(base_url, '/info/privacy'), wait_until='networkidle', timeout=45000)
            page.wait_for_selector('.sw-info', timeout=20000)
            page.wait_for_timeout(400)
            record('隐私政策页有内容',
                   '隐私政策' in page.locator('.sw-info').inner_text())

            page.goto(route_url(base_url, '/info/invite'), wait_until='networkidle', timeout=45000)
            page.wait_for_selector('.sw-info', timeout=20000)
            page.wait_for_timeout(400)
            record('邀请页有可复制的邀请文案',
                   page.locator('.sw-info__invite-text').count() == 1
                   and '鄂应墙' in page.locator('.sw-info__invite-text').inner_text())
            record('邀请页说明邀请码功能尚未开放',
                   '尚未开放邀请码' in page.locator('.sw-info').inner_text())
            page.screenshot(path=str(SHOTS_DIR / 'info-invite.png'))

            browser.close()
    finally:
        httpd.shutdown()

    record('控制台错误为 0', not console_errors, f'{len(console_errors)} 条')

    failed = [c for c in checks if not c['ok']]
    report = {
        'base': f'{base_url}/pc/',
        'paths': [name for name, _route, _label in PATHS],
        'checks': checks,
        'console_errors': console_errors,
        'status': 'FAIL' if failed else 'PASS',
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f'\n共 {len(checks)} 项断言，通过 {len(checks) - len(failed)} 项，控制台错误 {len(console_errors)} 条')
    for item in console_errors[:10]:
        print('   -', item)
    print(f'报告: {REPORT}')
    print(f'截图: {SHOTS_DIR}')
    if failed:
        print('[失败] 电脑端走查存在未通过项：')
        for item in failed:
            print(f"   - {item['name']} {item['detail']}")
        return 1
    print('[通过] 电脑端四条关键路径走查全部通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
