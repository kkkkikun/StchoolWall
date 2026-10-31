#!/usr/bin/env python3
"""
SchoolWall 学生端 H5 桌面（1280×800）与平板（768×1024）响应式回归走查
（独立脚本；Mock 数据与断言工具共享自 h5_mock_api.py，单一数据源）

每个视口串行覆盖（单个 Headless Chromium 实例）：
  1. 首页加载 + 分类 Tab 切换（亮色）
  2. 十大热帖榜单二级页 + CustomNavBar 返回
  3. 搜索面板 / 结果 / 空态（亮色）
  4. 帖子详情（正文/评论/固定输入栏遮挡/横向溢出，亮色）
  5. 我的页面 + 登录弹窗（打开/空提交校验/注册/找回/关闭）
  6. 设置页 + 主题切换（暗色生效）
  7. 暗色首页可读性（文字令牌色断言）
  8. 暗色帖子详情（meta 色令牌 + 溢出）

记录每场景实际宽度测量（文档宽、卡片宽、tab-bar 宽）供布局审查。
Mock 范围：**/api/v1/** 全部本地拦截（数据同移动端走查），不访问真实后端。
产物：ci-artifacts/ui-walkthrough/report-desktop.json + desktop-*.png / tablet-*.png
任一断言失败 -> 场景 FAIL，脚本退出码非零。
"""

import json
import os
import sys
import time
import traceback
from playwright.sync_api import sync_playwright

from h5_walkthrough_server import create_server

from h5_mock_api import (
    handle_api,
    assert_no_horizontal_overflow,
    assert_bottom_bar_not_blocking,
    assert_element_contrast,
    assert_token_color,
)

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

# ---------------------------------------------------------------- 报告
report = {
    'task': 'student H5 desktop(1280x800) & tablet(768x1024) responsive walkthrough',
    'date_utc': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
    'base_url': base_url,
    'browser': 'chromium(headless, single instance, serial)',
    'mock_scope': '**/api/v1/** intercepted locally (shared h5_mock_api fixtures); no real backend, no real credentials',
    'scenarios': [],
    'screenshots': [],
    'overall': 'PASS',
}

def record(scenario, viewport, theme, status, assertions=None, error=None, screenshots=None):
    report['scenarios'].append({
        'scenario': scenario, 'viewport': viewport, 'theme': theme, 'status': status,
        'assertions': assertions or {}, 'error': error, 'screenshots': screenshots or [],
    })
    if screenshots:
        report['screenshots'].extend(screenshots)
    if status != 'PASS':
        report['overall'] = 'FAIL'

class ScenarioFailure(Exception):
    pass

def check(cond, msg):
    if not cond:
        raise ScenarioFailure(msg)

def shot(page, filename):
    page.screenshot(path=f'{ARTIFACTS_DIR}/{filename}')
    return filename

def layout_metrics(page):
    return page.evaluate('''() => {
        const d = document.documentElement;
        const card = document.querySelector('.feed-card');
        const tabBar = document.querySelector('.tab-bar');
        const cardRect = card ? card.getBoundingClientRect() : null;
        const tabRect = tabBar ? tabBar.getBoundingClientRect() : null;
        return {
            docClientWidth: d.clientWidth,
            docScrollWidth: d.scrollWidth,
            feedCardWidth: cardRect ? Math.round(cardRect.width) : null,
            feedCardLeft: cardRect ? Math.round(cardRect.left) : null,
            tabBarWidth: tabRect ? Math.round(tabRect.width) : null,
        };
    }''')

def run_viewpoint_suite(browser, vp_label, width, height):
    """对视口执行完整亮色+暗色串行走查。"""
    ctx = browser.new_context(viewport={'width': width, 'height': height})
    page = ctx.new_page()
    page.route('**/api/v1/**', handle_api)

    # ---------------- 1. 首页亮色 + 分类切换 ----------------
    name = f'{vp_label}-home-light'
    print(f'\n--- [{vp_label}] 首页亮色 + 分类切换 ---')
    try:
        page.goto(f'{base_url}/#/pages/index/index')
        page.wait_for_selector('.feed-card', timeout=8000)
        page.wait_for_timeout(800)
        feed_count = page.locator('.feed-card').count()
        check(feed_count >= 1, '首页 Feed 卡片应渲染')
        tabs = page.locator('.tab-bar .tab-item')
        check(tabs.count() >= 5, f'底部 tab-bar 应有 5 项，实际 {tabs.count()}')
        # 分类切换（首页顶部分类 Tab）
        cat_tabs = page.locator('.cat-tab, .category-tab, .tabs .tab')
        if cat_tabs.count() > 1:
            cat_tabs.nth(1).click()
            page.wait_for_timeout(800)
            check(page.locator('.feed-card').count() >= 1, '分类切换后 Feed 应继续渲染')
        m = layout_metrics(page)
        check(m['docScrollWidth'] <= m['docClientWidth'] + 2, f'首页横向溢出: {m}')
        s1 = shot(page, f'{name}.png')
        print(f'   [通过] Feed {feed_count} 张卡片，布局测量: {m}')
        record(name, f'{width}x{height}', 'light', 'PASS',
               assertions={'feed_cards': feed_count, 'category_switch_ok': True, 'metrics': m},
               screenshots=[s1])
    except Exception as e:
        print(f'   [失败] {e}')
        record(name, f'{width}x{height}', 'light', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

    # ---------------- 2. 十大热帖 + 返回 ----------------
    name = f'{vp_label}-hot-list'
    print(f'--- [{vp_label}] 十大热帖榜单 + 返回 ---')
    try:
        page.goto(f'{base_url}/#/pages/index/index')
        page.wait_for_selector('.hot-posts-section .hot-more', timeout=8000)
        page.locator('.hot-posts-section .hot-more').click()
        page.wait_for_timeout(1500)
        rows = page.locator('.rank-row')
        check(rows.count() == 10, f'热帖榜单应 10 条，实际 {rows.count()}')
        for i in range(10):
            title = rows.nth(i).locator('.title').inner_text().strip()
            views = rows.nth(i).locator('.views').inner_text().strip()
            check(title and '浏览' in views, f'第{i+1}条标题/浏览数异常: {title} / {views}')
        assert_no_horizontal_overflow(page, f'{vp_label} 热帖榜单')
        s1 = shot(page, f'{name}.png')
        # CustomNavBar 返回首页
        back_btn = page.locator('.custom-nav-bar .back-trigger, .nav-left, .back-btn')
        if back_btn.count() > 0:
            back_btn.first.click()
        else:
            page.evaluate('window.history.back()')
        page.wait_for_timeout(1200)
        check(page.locator('.feed-card').count() >= 1, '返回首页后 Feed 应重新可见')
        print('   [通过] 10 条榜单渲染完整，返回首页正常')
        record(name, f'{width}x{height}', 'light', 'PASS',
               assertions={'rank_rows': 10, 'back_to_home': True}, screenshots=[s1])
    except Exception as e:
        print(f'   [失败] {e}')
        record(name, f'{width}x{height}', 'light', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

    # ---------------- 3. 搜索页（亮色） ----------------
    name = f'{vp_label}-search-light'
    print(f'--- [{vp_label}] 搜索面板/结果/空态 ---')
    try:
        page.goto(f'{base_url}/#/pages/search/index')
        page.wait_for_selector('.search-bar', timeout=8000)
        page.wait_for_timeout(800)
        check(page.locator('.search-bar input').is_visible(), '搜索输入框应可见')
        check(page.locator('.hot-pill').count() > 0, '热门探索标签应渲染')
        assert_no_horizontal_overflow(page, f'{vp_label} 搜索面板')
        s1 = shot(page, f'{name}.png')

        page.fill('.search-bar input', '考研')
        page.locator('.search-btn').click()
        page.wait_for_timeout(800)
        check(page.locator('.feed-card').count() >= 1, '搜索结果应渲染')
        assert_no_horizontal_overflow(page, f'{vp_label} 搜索结果')
        s2 = shot(page, f'{vp_label}-search-results.png')

        page.fill('.search-bar input', '无结果测试词xyz')
        page.locator('.search-btn').click()
        page.wait_for_timeout(800)
        check(page.locator('.empty-text').is_visible(), '空态提示应可见')
        print('   [通过] 面板/结果/空态正常，无横向溢出')
        record(name, f'{width}x{height}', 'light', 'PASS',
               assertions={'hot_pills': page.locator('.hot-pill').count(),
                           'results_rendered': True, 'empty_state': True},
               screenshots=[s1, s2])
    except Exception as e:
        print(f'   [失败] {e}')
        record(name, f'{width}x{height}', 'light', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

    # ---------------- 4. 帖子详情（亮色） ----------------
    name = f'{vp_label}-post-detail-light'
    print(f'--- [{vp_label}] 帖子详情（亮色） ---')
    try:
        page.goto(f'{base_url}/#/pages/post-detail/index?id=1')
        page.wait_for_selector('.content-text', timeout=8000)
        page.wait_for_timeout(1000)
        check(page.locator('.author .nickname').is_visible(), '作者昵称应可见')
        check(page.locator('.action-bar .act').count() == 4, '互动栏应为 4 项')
        check(page.locator('.comments .comment').count() >= 1, '评论列表应渲染')
        check(page.locator('.comment-input-bar').is_visible(), '底部评论输入栏应可见')
        assert_no_horizontal_overflow(page, f'{vp_label} 帖子详情')
        assert_bottom_bar_not_blocking(page, f'{vp_label} 帖子详情')
        m = layout_metrics(page)
        s1 = shot(page, f'{name}.png')
        print(f'   [通过] 正文/评论/输入栏正常，无遮挡无溢出')
        record(name, f'{width}x{height}', 'light', 'PASS',
               assertions={'comments': page.locator('.comments .comment').count(),
                           'bottom_bar_clear': True, 'metrics': m}, screenshots=[s1])
    except Exception as e:
        print(f'   [失败] {e}')
        record(name, f'{width}x{height}', 'light', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

    # ---------------- 5. 我的页面 + 独立登录页 ----------------
    name = f'{vp_label}-auth-page'
    print(f'--- [{vp_label}] 我的页面 + 登录页 ---')
    try:
        page.goto(f'{base_url}/#/pages/mine/index')
        page.wait_for_selector('.dev-login-row', timeout=8000)
        page.wait_for_timeout(500)
        assert_no_horizontal_overflow(page, f'{vp_label} 我的页面')

        page.locator('.dev-capsule:has-text("登录 / 注册")').click()
        page.wait_for_selector('.auth-form', timeout=5000)
        page.wait_for_timeout(300)
        check(page.locator('.auth-hint').inner_text().strip() == '使用已注册的账号登录', '登录页默认提示应为「使用已注册的账号登录」')
        check(page.locator('.auth-submit').inner_text().strip() == '进入鄂应墙', '主按钮应为「进入鄂应墙」')
        # 登录表单不得超出视口
        card_box = page.locator('.auth-form').bounding_box()
        check(card_box['width'] <= width, f'登录表单超出视口: {card_box["width"]} > {width}')

        # 空提交校验（不发出请求即提示）
        page.locator('.auth-submit').click()
        page.wait_for_timeout(600)
        err = page.locator('.auth-error-text')
        check(err.count() > 0 and '账号和密码' in err.inner_text(), '空提交应有就地校验提示')

        # 注册/找回模式切换
        page.locator('.auth-tab:has-text("注册")').click()
        page.wait_for_timeout(300)
        check(page.locator('.auth-hint').inner_text().strip() == '注册密码至少 10 位', '注册模式提示异常')
        page.locator('.auth-link:has-text("忘记密码")').click()
        page.wait_for_timeout(300)
        check(page.locator('.auth-input').count() == 3, '找回模式应有 3 个输入框')
        s1 = shot(page, f'{name}.png')

        page.locator('.back-trigger').click()
        page.wait_for_timeout(400)
        check(page.locator('.auth-form').count() == 0, '返回应离开登录页')
        print(f'   [通过] 登录页结构/校验/模式切换/返回正常，表单宽 {card_box["width"]:.0f}px')
        record(name, f'{width}x{height}', 'light', 'PASS',
               assertions={'form_width': round(card_box['width'], 1), 'modes_ok': True,
                           'validation_error': True, 'back_to_mine': True}, screenshots=[s1])
    except Exception as e:
        print(f'   [失败] {e}')
        record(name, f'{width}x{height}', 'light', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

    # ---------------- 6. 设置页 + 主题切换 ----------------
    name = f'{vp_label}-settings-theme'
    print(f'--- [{vp_label}] 设置页 + 暗色切换 ---')
    try:
        page.goto(f'{base_url}/#/pages/mine/index')
        page.wait_for_selector('.gear-btn', timeout=8000)
        page.locator('.gear-btn').click()
        page.wait_for_timeout(1200)
        check(page.locator('.group-card').count() >= 1, '设置页分组卡片应渲染')
        sw = page.locator('.cell switch, .cell uni-switch')
        check(sw.count() > 0, '深色模式开关应存在')
        sw.first.click()
        page.wait_for_timeout(800)
        is_dark = page.evaluate("() => document.documentElement.classList.contains('theme-dark')")
        check(is_dark, '切换后 html 应带 theme-dark 类')
        s1 = shot(page, f'{name}.png')
        print('   [通过] 设置页渲染正常，暗色主题切换生效')
        record(name, f'{width}x{height}', 'dark', 'PASS',
               assertions={'theme_dark_class': True}, screenshots=[s1])
    except Exception as e:
        print(f'   [失败] {e}')
        record(name, f'{width}x{height}', 'light->dark', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

    # ---------------- 7. 暗色首页可读性 ----------------
    name = f'{vp_label}-home-dark'
    print(f'--- [{vp_label}] 暗色首页可读性 ---')
    try:
        page.goto(f'{base_url}/#/pages/index/index')
        page.wait_for_selector('.feed-card', timeout=8000)
        page.wait_for_timeout(800)
        is_dark = page.evaluate("() => document.documentElement.classList.contains('theme-dark')")
        check(is_dark, '暗色场景 html 应带 theme-dark 类（主题应跨页面持久）')
        text_color = assert_token_color(
            page, '.feed-card .feed-text', '--text-1', '暗色正文', f'{vp_label} 暗色首页')
        assert_element_contrast(page, '.feed-card .feed-text', 4.5, '暗色正文', f'{vp_label} 暗色首页')
        assert_no_horizontal_overflow(page, f'{vp_label} 暗色首页')
        s1 = shot(page, f'{name}.png')
        print(f'   [通过] 暗色正文颜色 {text_color}，无溢出')
        record(name, f'{width}x{height}', 'dark', 'PASS',
               assertions={'text_color': text_color}, screenshots=[s1])
    except Exception as e:
        print(f'   [失败] {e}')
        record(name, f'{width}x{height}', 'dark', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

    # ---------------- 8. 暗色帖子详情 ----------------
    name = f'{vp_label}-post-detail-dark'
    print(f'--- [{vp_label}] 暗色帖子详情 ---')
    try:
        page.goto(f'{base_url}/#/pages/post-detail/index?id=1')
        page.wait_for_selector('.content-text', timeout=8000)
        page.wait_for_timeout(1000)
        meta_color = page.locator('.meta').evaluate('el => window.getComputedStyle(el).color')
        # 不写死具体色值：直接断言实际对比度达标（令牌微调后断言依然成立）
        assert_element_contrast(page, '.meta', 4.5, '暗色详情 meta', f'{vp_label} 暗色帖子详情')
        assert_no_horizontal_overflow(page, f'{vp_label} 暗色帖子详情')
        assert_bottom_bar_not_blocking(page, f'{vp_label} 暗色帖子详情')
        s1 = shot(page, f'{name}.png')
        print(f'   [通过] 暗色详情 meta 颜色 {meta_color}，输入栏无遮挡')
        record(name, f'{width}x{height}', 'dark', 'PASS',
               assertions={'meta_color': meta_color}, screenshots=[s1])
    except Exception as e:
        print(f'   [失败] {e}')
        record(name, f'{width}x{height}', 'dark', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')

    ctx.close()

exit_code = 0
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        run_viewpoint_suite(browser, 'desktop', 1280, 800)
        run_viewpoint_suite(browser, 'tablet', 768, 1024)
        browser.close()
except Exception as e:
    print(f'\n[致命错误] {e}', file=sys.stderr)
    report['overall'] = 'FAIL'
    report['fatal'] = f'{e}\n{traceback.format_exc(limit=3)}'
finally:
    httpd.shutdown()

report_path = f'{ARTIFACTS_DIR}/report-desktop.json'
with open(report_path, 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

passed = sum(1 for s in report['scenarios'] if s['status'] == 'PASS')
print(f'\n========================================================')
print(f'桌面/平板走查结束: {passed}/{len(report["scenarios"])} 场景通过，总体 {report["overall"]}')
print(f'报告: {report_path}')
print(f'========================================================')

if report['overall'] != 'PASS':
    sys.exit(1)
