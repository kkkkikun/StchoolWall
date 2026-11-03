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

# 四条关键路径：名字、路由、场景说明
PATHS = [
    ('feed', '/', '信息流'),
    ('post-detail', '/post/1', '帖子详情'),
    ('login', '/login', '登录'),
    ('publish', '/publish', '发帖'),
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
