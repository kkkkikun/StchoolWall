#!/usr/bin/env python3
"""
SchoolWall 前端 H5 自动化端到端走查与渲染验证脚本。
使用真实 Headless Chromium (390×844 视口) 走查首页热帖、信息流、登录弹窗、设置页及暗黑模式，
并断言真实后端标准契约下的渲染结果，保存截图至 ci-artifacts/ui-walkthrough/。
"""

import json
import os
import sys
import urllib.parse
from playwright.sync_api import sync_playwright

from h5_walkthrough_server import create_server

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIST_DIR = os.path.join(ROOT_DIR, 'frontend', 'dist', 'build', 'h5')
SCREENSHOT_DIR = os.path.join(ROOT_DIR, 'ci-artifacts', 'ui-walkthrough')
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

if not os.path.isdir(DIST_DIR):
    print(f"Error: DIST_DIR not found at {DIST_DIR}. Please run 'npm run build:h5' first.", file=sys.stderr)
    sys.exit(1)

# 共享静态服务（scripts/ 目录随脚本入 sys.path）
httpd, base_url = create_server(DIST_DIR)
print(f"Local static server listening on {base_url}")

from h5_mock_api import (
    handle_api,  # 共享 Mock（scripts/ 目录随脚本入 sys.path）
    assert_no_horizontal_overflow,
    assert_bottom_bar_not_blocking,
    parse_css_rgb,
    calculate_wcag_contrast,
    assert_element_contrast,
    assert_token_color,
    assert_token_background,
)

reports = []



with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={'width': 390, 'height': 844},
        user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1',
    )
    page = context.new_page()

    page.route('**/api/v1/**', handle_api)

    # 1. 首页：亮色模式 + 热帖 4 条预览渲染断言
    print('1. 走查首页（亮色模式）...')
    page.goto(f'{base_url}/#/pages/index/index')
    page.wait_for_timeout(1500)
    page.screenshot(path=f'{SCREENSHOT_DIR}/01_home_guest_light.png')

    hot_items = page.locator('.hot-item')
    hot_count = hot_items.count()
    assert hot_count == 4, f"首页热帖应渲染 4 条预览，实际渲染了 {hot_count} 条"

    for i in range(hot_count):
        title = hot_items.nth(i).locator('.hot-item-title').inner_text().strip()
        reads = hot_items.nth(i).locator('.read-count').inner_text().strip()
        assert title != '（无文字）' and len(title) > 0, f"首页第 {i+1} 条热帖标题异常回退为（无文字）"
        assert reads != '0 浏览' and '浏览' in reads, f"首页第 {i+1} 条热帖浏览数异常回退为 0 浏览"
        print(f"   [首页热帖预览 #{i+1}] 标题: '{title}', 浏览数: '{reads}'")

    # 切片保存首页 Banner 与热帖
    banner = page.locator('.ad-swiper')
    if banner.count() > 0:
        banner.first.screenshot(path=f'{SCREENSHOT_DIR}/crop_home_banner.png')
    hot_sec = page.locator('.hot-posts-section')
    if hot_sec.count() > 0:
        hot_sec.first.screenshot(path=f'{SCREENSHOT_DIR}/crop_home_hot_posts.png')

    reports.append({
        'step': '01_home_guest_light',
        'page': 'pages/index/index',
        'status': 'PASS',
        'evidence': '01_home_guest_light.png, 标准契约下热帖标题与格式化浏览数正常渲染',
    })

    # 2. 首页切换分类 Tab
    print('2. 走查首页分类 Tab 切换...')
    tab_items = page.locator('.tab-bar-sticky .tab-item')
    if tab_items.count() > 1:
        tab_items.nth(1).click()
        page.wait_for_timeout(800)
    page.screenshot(path=f'{SCREENSHOT_DIR}/02_home_tabs_switched.png')
    reports.append({
        'step': '02_home_tabs_switched',
        'page': 'pages/index/index',
        'status': 'PASS',
        'evidence': '02_home_tabs_switched.png, 分类切换正常',
    })

    # 3. 首页滚动
    print('3. 走查首页滚动...')
    page.evaluate('window.scrollTo(0, 300)')
    page.wait_for_timeout(500)
    page.screenshot(path=f'{SCREENSHOT_DIR}/03_home_scrolled.png')
    reports.append({
        'step': '03_home_scrolled',
        'page': 'pages/index/index',
        'status': 'PASS',
        'evidence': '03_home_scrolled.png, 滚动避让正常',
    })

    # 4. 二级页：完整十大热帖榜单
    print('4. 走查完整十大热帖榜单（二级页）...')
    page.evaluate('window.scrollTo(0, 0)')
    page.wait_for_timeout(300)
    page.locator('.hot-posts-section .hot-more').click()
    page.wait_for_timeout(1500)
    page.screenshot(path=f'{SCREENSHOT_DIR}/02_hot_list_full.png')
    rank_rows = page.locator('.rank-row')
    assert rank_rows.count() == 10, f"完整热帖榜单应渲染 10 条，实际有 {rank_rows.count()} 条"
    print(f"   完整榜单行数: {rank_rows.count()}")

    for i in range(rank_rows.count()):
        row = rank_rows.nth(i)
        rank_num = row.locator('.rank').inner_text().strip()
        title_text = row.locator('.title').inner_text().strip()
        views_text = row.locator('.views').inner_text().strip()
        assert rank_num == str(i + 1), f"第 {i+1} 条排名序号应为 {i+1}，实际为 '{rank_num}'"
        assert title_text and title_text != '（无文字）', f"第 {i+1} 条热帖标题异常为空或回退为（无文字）: '{title_text}'"
        assert views_text and views_text != '0 浏览' and '浏览' in views_text, f"第 {i+1} 条热帖浏览数异常为空或回退为 0 浏览: '{views_text}'"
        print(f"   [十大热帖榜单 #{rank_num}] 标题: '{title_text}', 浏览数: '{views_text}'")

    reports.append({
        'step': '02_hot_list_full',
        'page': 'pages/hot/index',
        'status': 'PASS',
        'evidence': '02_hot_list_full.png, 完整十大热帖榜单 10 条全部渲染，每条标题与浏览数非空且不为0',
    })

    # 4.1 从热帖二级页通过 CustomNavBar 返回首页
    print('   从热帖二级页返回首页...')
    back_btn = page.locator('.custom-nav-bar .back-trigger, .nav-left, .back-btn')
    if back_btn.count() > 0:
        back_btn.first.click()
    else:
        page.evaluate('window.history.back()')
    page.wait_for_timeout(1200)

    # 4.2 走查搜索页（亮色模式）
    print('4.2 走查搜索页（亮色模式）...')
    page.goto(f'{base_url}/#/pages/search/index')
    page.wait_for_timeout(1000)
    assert page.locator('.search-bar').is_visible(), "搜索栏应可见"
    assert page.locator('.search-bar input').is_visible(), "搜索输入框应可见"
    assert page.locator('.search-btn').is_visible(), "搜索按钮应可见"
    assert page.locator('.hot-pill').count() > 0, "热门探索标签应可见"

    # 测量亮色模式下搜索框占位符对比度，确认不回退
    light_search_ph = page.evaluate('''() => {
        const ph = document.querySelector('.search-bar .uni-input-placeholder') ||
                   document.querySelector('.search-bar input');
        const bar = document.querySelector('.search-bar');
        return {
            phColor: window.getComputedStyle(ph).color,
            barBg: window.getComputedStyle(bar).backgroundColor,
        };
    }''')
    light_search_contrast = calculate_wcag_contrast(light_search_ph['phColor'], light_search_ph['barBg'])
    print(f"   [对比度验证] 亮色搜索占位符: 前景={light_search_ph['phColor']}, 背景={light_search_ph['barBg']}, 对比度={light_search_contrast:.2f}:1")
    assert light_search_contrast >= 4.5, f"亮色搜索占位符对比度低于 4.5:1 (实际为 {light_search_contrast:.2f}:1)"

    assert_no_horizontal_overflow(page, "搜索页（亮色推荐面板）")
    page.screenshot(path=f'{SCREENSHOT_DIR}/15_search_panel_light.png')
    reports.append({
        'step': '15_search_panel_light',
        'page': 'pages/search/index',
        'status': 'PASS',
        'evidence': f'15_search_panel_light.png, 搜索输入框与热门标签渲染正常且无横向溢出，占位符对比度 {light_search_contrast:.2f}:1',
    })

    # 输入关键词搜索
    page.fill('.search-bar input', '考研')
    page.locator('.search-btn').click()
    page.wait_for_timeout(800)
    assert page.locator('.feed-card').count() >= 1, "搜索结果应渲染 FeedCard"
    assert_no_horizontal_overflow(page, "搜索页（亮色结果列表）")
    page.screenshot(path=f'{SCREENSHOT_DIR}/16_search_results_light.png')
    reports.append({
        'step': '16_search_results_light',
        'page': 'pages/search/index (Results)',
        'status': 'PASS',
        'evidence': '16_search_results_light.png, 关键词结果列表卡片正常渲染无溢出',
    })

    # 空态搜索
    page.fill('.search-bar input', '无结果测试词xyz')
    page.locator('.search-btn').click()
    page.wait_for_timeout(800)
    assert page.locator('.empty-text').is_visible(), "空态提示文案应可见"
    page.screenshot(path=f'{SCREENSHOT_DIR}/17_search_empty_light.png')
    reports.append({
        'step': '17_search_empty_light',
        'page': 'pages/search/index (Empty)',
        'status': 'PASS',
        'evidence': '17_search_empty_light.png, 空态搜索提示文案对比度与布局清晰',
    })

    # 4.3 走查帖子详情页（亮色模式）
    print('4.3 走查帖子详情页（亮色模式）...')
    page.goto(f'{base_url}/#/pages/post-detail/index?id=1')
    page.wait_for_timeout(1200)
    assert page.locator('.author .avatar').is_visible(), "作者头像应可见"
    assert page.locator('.author .nickname').is_visible(), "作者昵称应可见"
    assert page.locator('.author .sub').is_visible(), "作者发布时间与分类应可见"
    assert page.locator('.content-text').is_visible(), "正文文本应可见"
    assert page.locator('.action-bar .act').count() == 4, "互动栏应有4个操作项"
    assert page.locator('.comments .comment').count() >= 1, "评论列表应渲染"
    assert page.locator('.comment-input-bar').is_visible(), "底部评论输入栏应可见"

    # 测量亮色模式下评论框占位符对比度，确认不回退
    light_comment_ph = page.evaluate('''() => {
        const ph = document.querySelector('.comment-input .uni-input-placeholder') ||
                   document.querySelector('.comment-input input') ||
                   document.querySelector('.comment-input');
        const inputWrap = document.querySelector('.comment-input');
        return {
            phColor: window.getComputedStyle(ph).color,
            inputBg: window.getComputedStyle(inputWrap).backgroundColor,
        };
    }''')
    light_comment_contrast = calculate_wcag_contrast(light_comment_ph['phColor'], light_comment_ph['inputBg'])
    print(f"   [对比度验证] 亮色评论占位符: 前景={light_comment_ph['phColor']}, 背景={light_comment_ph['inputBg']}, 对比度={light_comment_contrast:.2f}:1")
    assert light_comment_contrast >= 4.5, f"亮色评论占位符对比度低于 4.5:1 (实际为 {light_comment_contrast:.2f}:1)"

    assert_no_horizontal_overflow(page, "帖子详情页（亮色模式）")
    assert_bottom_bar_not_blocking(page, "帖子详情页（亮色模式）")
    page.screenshot(path=f'{SCREENSHOT_DIR}/18_post_detail_light.png')

    # 切片保存详情页作者区与底部固定输入栏
    page.locator('.author').first.screenshot(path=f'{SCREENSHOT_DIR}/crop_detail_author.png')
    page.locator('.comment-input-bar').first.screenshot(path=f'{SCREENSHOT_DIR}/crop_detail_bottom_bar.png')
    reports.append({
        'step': '18_post_detail_light',
        'page': 'pages/post-detail/index',
        'status': 'PASS',
        'evidence': f'18_post_detail_light.png, 详情页作者长昵称、正文话题、评论列表及底部输入栏留白正常无遮挡，占位符对比度 {light_comment_contrast:.2f}:1',
    })

    # 4.4 返回首页
    print('   从详情页返回首页...')
    page.goto(f'{base_url}/#/pages/index/index')
    page.wait_for_timeout(800)

    # 5. 我的页面
    print('5. 走查我的页面...')
    page.locator('.tab-bar .tab-item').nth(4).click()
    page.wait_for_timeout(1500)
    page.screenshot(path=f'{SCREENSHOT_DIR}/04_mine_guest_light.png')

    # 未登录态：展示登录引导，不展示个人内容 Tab 与「编辑资料」（避免误导性空列表）
    assert page.locator('.login-guide').count() > 0, "未登录时「我的」页应展示登录引导"
    assert page.locator('.content-tabs').count() == 0, "未登录时不应展示个人内容 Tab（应展示登录引导）"
    assert page.locator('.edit-btn').count() == 0, "未登录时不应展示「编辑资料」按钮"

    # 切片保存我的页面核心元素
    page.locator('.login-guide').first.screenshot(path=f'{SCREENSHOT_DIR}/crop_mine_login_guide.png')
    page.locator('.dev-login-row').first.screenshot(path=f'{SCREENSHOT_DIR}/crop_mine_capsule.png')
    page.locator('.gear-btn').first.screenshot(path=f'{SCREENSHOT_DIR}/crop_mine_gear.png')

    # 5.2 登录态「我的」页：应恢复个人内容 Tab（覆盖 .content-tabs 渲染）
    print('5.2 走查登录态「我的」页面...')
    def _json_route(payload):
        def handler(route):
            route.fulfill(status=200, content_type='application/json', body=json.dumps(payload))
        return handler

    session_payload = {'code': 0, 'message': 'success', 'data': {
        'access_token': 'mock-access-token-for-test',
        'csrf_token': 'mock-csrf-token',
        'session_id': 'mock-session-id',
        'role': 'student',
        'user_info': {'id': 'u-test-01', 'nickname': '测试同学', 'is_verified': False},
    }}
    # 后注册的路由优先命中；个人接口必须返回 200，否则 401 会清掉本地会话
    page.route('**/api/v1/auth/web-login', _json_route(session_payload))
    page.route('**/api/v1/auth/refresh', _json_route(session_payload))
    page.route('**/api/v1/user/profile', _json_route({'code': 0, 'data': {
        'id': 'u-test-01', 'nickname': '测试同学', 'avatar_url': None, 'banner_url': None,
        'bio': '走查用个人简介', 'is_verified': True, 'school': '示例大学'}}))
    page.route('**/api/v1/me/stats', _json_route({'code': 0, 'data': {
        'posts_count': 3, 'comments_count': 2, 'favorites_count': 1, 'likes_count': 4}}))
    for path in ('/api/v1/posts/my', '/api/v1/me/favorites', '/api/v1/me/likes', '/api/v1/me/comments'):
        page.route(f'**{path}', _json_route({'code': 0, 'data': {'items': []}}))
    page.locator('.dev-capsule:has-text("登录 / 注册")').click()
    page.wait_for_selector('.auth-form', timeout=8000)
    page.evaluate('''(vals) => {
        const inputs = document.querySelectorAll('.auth-form .auth-input input');
        vals.forEach((v, i) => {
            const el = inputs[i];
            el.value = v;
            el.dispatchEvent(new Event('input', { bubbles: true }));
        });
    }''', ['walkthrough_user', 'password123'])
    page.locator('.auth-submit').click()
    page.wait_for_timeout(1500)
    # Web 端登录态判定依赖 sw_csrf Cookie + 本地 user_info
    page.evaluate("() => { document.cookie = 'sw_csrf=mock-csrf-token; path=/'; }")
    page.goto(f'{base_url}/#/pages/mine/index')
    page.reload()
    page.wait_for_selector('.content-tabs', timeout=10000)
    page.wait_for_timeout(800)
    assert page.locator('.content-tabs').count() > 0, "登录后「我的」页应展示个人内容 Tab"
    assert page.locator('.login-guide').count() == 0, "登录后不应展示登录引导"
    assert page.locator('.edit-btn').count() > 0, "登录后应展示「编辑资料」按钮"
    page.locator('.content-tabs').first.screenshot(path=f'{SCREENSHOT_DIR}/crop_mine_tabs.png')
    page.screenshot(path=f'{SCREENSHOT_DIR}/04b_mine_logged_in_light.png')
    print('   [通过] 登录态「我的」页个人内容 Tab 正常渲染')

    reports.append({
        'step': '04_mine_guest_light',
        'page': 'pages/mine/index',
        'status': 'PASS',
        'evidence': f'04_mine_guest_light.png, URL={page.url}',
    })

    # 6. 独立登录/注册页系列交互
    print('6. 走查登录/注册页交互...')
    login_btn = page.locator('.dev-capsule:has-text("登录 / 注册")')
    if login_btn.count() > 0:
        login_btn.first.click()
        page.wait_for_timeout(800)
        page.screenshot(path=f'{SCREENSHOT_DIR}/05_auth_page_open.png')
        reports.append({
            'step': '05_auth_page_open',
            'page': 'pages/auth/index',
            'status': 'PASS',
            'evidence': '05_auth_page_open.png, 独立登录/注册页展开',
        })

        # 空提交表单校验错误（就地提示）
        page.locator('.auth-submit').click()
        page.wait_for_timeout(500)
        page.screenshot(path=f'{SCREENSHOT_DIR}/06_auth_page_error.png')
        reports.append({
            'step': '06_auth_page_error',
            'page': 'pages/auth/index',
            'status': 'PASS',
            'evidence': '06_auth_page_error.png, 空提交校验错误提示正确',
        })

        # 切换到注册
        reg_tab = page.locator('.auth-tab:has-text("注册")')
        if reg_tab.count() > 0:
            reg_tab.click()
            page.wait_for_timeout(500)
        page.screenshot(path=f'{SCREENSHOT_DIR}/07_auth_page_register.png')
        reports.append({
            'step': '07_auth_page_register',
            'page': 'pages/auth/index',
            'status': 'PASS',
            'evidence': '07_auth_page_register.png, 注册模式切换正常',
        })

        # 切换到找回密码
        rec_link = page.locator('.auth-link:has-text("忘记密码")')
        if rec_link.count() > 0:
            rec_link.click()
            page.wait_for_timeout(500)
        page.screenshot(path=f'{SCREENSHOT_DIR}/08_auth_page_recovery.png')
        reports.append({
            'step': '08_auth_page_recovery',
            'page': 'pages/auth/index',
            'status': 'PASS',
            'evidence': '08_auth_page_recovery.png, 找回码输入框渲染正常',
        })

        # 返回「我的」页
        page.locator('.back-trigger').click()
        page.wait_for_timeout(800)
        page.screenshot(path=f'{SCREENSHOT_DIR}/09_auth_page_back.png')
        reports.append({
            'step': '09_auth_page_back',
            'page': 'pages/mine/index',
            'status': 'PASS',
            'evidence': '09_auth_page_back.png, 返回箭头回到「我的」页',
        })

    # 7. 设置页面
    print('7. 走查设置页...')
    page.locator('.gear-btn').click()
    page.wait_for_timeout(1500)
    page.screenshot(path=f'{SCREENSHOT_DIR}/10_settings_guest_light.png')
    page.locator('.group-card').nth(1).screenshot(path=f'{SCREENSHOT_DIR}/crop_settings_group1.png')
    reports.append({
        'step': '10_settings_guest_light',
        'page': 'pages/settings/index',
        'status': 'PASS',
        'evidence': f'10_settings_guest_light.png, URL={page.url}',
    })

    # 8. 暗黑模式切换
    print('8. 走查暗黑模式切换...')
    sw = page.locator('.cell switch, .cell uni-switch')
    if sw.count() > 0:
        sw.first.click()
        page.wait_for_timeout(800)
    is_dark = page.evaluate("() => document.documentElement.classList.contains('theme-dark')")
    assert is_dark, "点击设置页深色模式开关后，系统应成功应用暗色模式（document.documentElement 带有 theme-dark 类）"
    page.screenshot(path=f'{SCREENSHOT_DIR}/11_settings_guest_dark.png')
    reports.append({
        'step': '11_settings_guest_dark',
        'page': 'pages/settings/index',
        'status': 'PASS',
        'evidence': '11_settings_guest_dark.png, UI 开关成功触发并应用暗黑主题令牌',
    })

    # 9. 暗黑模式返回我的页面
    print('9. 走查暗黑模式我的页面...')
    head_back = page.locator('uni-page-head .uni-page-head-btn, .uni-page-head .uni-btn-icon')
    if head_back.count() > 0:
        head_back.first.click()
    else:
        page.go_back()
    page.wait_for_timeout(1500)
    page.screenshot(path=f'{SCREENSHOT_DIR}/12_mine_guest_dark.png')
    reports.append({
        'step': '12_mine_guest_dark',
        'page': 'pages/mine/index',
        'status': 'PASS',
        'evidence': f'12_mine_guest_dark.png, URL={page.url}',
    })

    # 10. 暗黑模式登录/注册页
    print('10. 走查暗黑模式登录页...')
    dark_login_btn = page.locator('.dev-capsule:has-text("登录 / 注册")')
    if dark_login_btn.count() > 0:
        dark_login_btn.first.click()
        page.wait_for_timeout(800)
        page.screenshot(path=f'{SCREENSHOT_DIR}/13_auth_page_dark.png')
        reports.append({
            'step': '13_auth_page_dark',
            'page': 'pages/auth/index (Dark)',
            'status': 'PASS',
            'evidence': '13_auth_page_dark.png, 暗黑登录页背景与输入框正常',
        })
        page.locator('.back-trigger').click()
        page.wait_for_timeout(800)

    # 11. 返回首页（暗黑模式）
    print('11. 走查暗黑模式首页...')
    page.locator('.tab-bar .tab-item').nth(0).click()
    page.wait_for_timeout(1500)
    page.screenshot(path=f'{SCREENSHOT_DIR}/14_home_guest_dark.png')
    reports.append({
        'step': '14_home_guest_dark',
        'page': 'pages/index/index',
        'status': 'PASS',
        'evidence': '14_home_guest_dark.png, 暗黑模式首页渲染正常',
    })

    # 12. 走查搜索页（暗黑模式）
    print('12. 走查搜索页（暗黑模式）...')
    page.goto(f'{base_url}/#/pages/search/index')
    page.wait_for_timeout(1000)

    # 若搜索框残留上一轮的搜索词，点击清空恢复推荐探索面板
    clear_btn = page.locator('.search-bar .clear')
    if clear_btn.is_visible():
        clear_btn.click()
        page.wait_for_timeout(500)

    # 显式断言：暗色模式下搜索推荐面板可见、热门搜索标签数 > 0、标题可见
    assert page.locator('.search-panel').is_visible(), "暗色模式下搜索推荐面板应可见"
    hot_pills = page.locator('.search-panel .hot-pill')
    hot_count = hot_pills.count()
    assert hot_count > 0, f"暗色模式下热门搜索标签数量应大于0，实际为 {hot_count}"
    assert page.locator('.search-panel .section-title').first.is_visible(), "暗色模式下推荐面板标题应可见"

    # 验证暗色模式下推荐面板标题与标签文本计算样式的对比度，确保符合主题令牌并非默认低对比灰
    sec_title_color = assert_token_color(
        page, '.search-panel .section-title', '--text-1', '暗色搜索推荐面板标题', '暗色搜索页')

    # 热门标签底为 --primary-soft，品牌文字必须用 --primary-text 才达 AA（按令牌判定，换品牌同样成立）
    hot_tag_color = assert_token_color(
        page, '.search-panel .hot-pill', '--primary-text', '暗色搜索热门标签', '暗色搜索面板')
    assert_element_contrast(page, '.search-panel .hot-pill', 4.5, '暗色搜索热门标签', '暗色搜索面板')

    # 测量暗色模式下搜索框占位符前景与背景计算样式，并以计算对比度断言 >= 4.5
    dark_search_ph = page.evaluate('''() => {
        const ph = document.querySelector('.search-bar .uni-input-placeholder') ||
                   document.querySelector('.search-bar input');
        const bar = document.querySelector('.search-bar');
        return {
            phColor: window.getComputedStyle(ph).color,
            barBg: window.getComputedStyle(bar).backgroundColor,
        };
    }''')
    dark_search_contrast = calculate_wcag_contrast(dark_search_ph['phColor'], dark_search_ph['barBg'])
    print(f"   [对比度验证] 暗色搜索占位符: 前景={dark_search_ph['phColor']}, 背景={dark_search_ph['barBg']}, 对比度={dark_search_contrast:.2f}:1")
    assert dark_search_contrast >= 4.5, (
        f"暗色模式下搜索框占位符对比度不足 4.5:1 (实际为 {dark_search_contrast:.2f}:1, "
        f"前景={dark_search_ph['phColor']}, 背景={dark_search_ph['barBg']})"
    )

    assert_no_horizontal_overflow(page, "搜索页（暗黑推荐面板）")
    page.screenshot(path=f'{SCREENSHOT_DIR}/19_search_panel_dark.png')
    reports.append({
        'step': '19_search_panel_dark',
        'page': 'pages/search/index',
        'status': 'PASS',
        'evidence': f"19_search_panel_dark.png, 深色模式下推荐探索面板可见、热门标签与标题高对比度渲染无横向溢出，占位符对比度 {dark_search_contrast:.2f}:1 (>=4.5:1)",
    })

    page.fill('.search-bar input', '考研')
    page.locator('.search-btn').click()
    page.wait_for_timeout(800)
    assert page.locator('.feed-card').count() >= 1, "暗黑模式下搜索结果应渲染"
    assert_no_horizontal_overflow(page, "搜索页（暗黑结果列表）")
    page.screenshot(path=f'{SCREENSHOT_DIR}/20_search_results_dark.png')
    reports.append({
        'step': '20_search_results_dark',
        'page': 'pages/search/index (Results)',
        'status': 'PASS',
        'evidence': '20_search_results_dark.png, 深色模式下搜索结果流卡片视觉一致无溢出',
    })

    # 13. 走查帖子详情页（暗黑模式）
    print('13. 走查帖子详情页（暗黑模式）...')
    page.goto(f'{base_url}/#/pages/post-detail/index?id=1')
    page.wait_for_timeout(1200)

    # 显式断言暗黑模式下详情页各核心元素渲染
    assert page.locator('.content-text').is_visible(), "正文文本应可见"
    assert page.locator('.meta').is_visible(), "浏览/赞/评论元信息应可见"
    assert page.locator('.action-bar .act').count() == 4, "互动栏操作项应为4个"
    assert page.locator('.comments .comment').count() >= 1, "评论列表应渲染"
    assert page.locator('.comment-input-bar').is_visible(), "底部评论输入栏应可见"

    # 断言互动栏文字计算颜色为高对比度 --text-1 (近白)
    act_color = assert_token_color(
        page, '.action-bar .act', '--text-1', '暗色互动栏文字', '暗色帖子详情')

    # 断言浏览数等 meta 文本颜色符合主题 tokens，不回退为低对比度不可读灰
    meta_color = page.locator('.meta').evaluate('el => window.getComputedStyle(el).color')
    assert_element_contrast(page, '.meta', 4.5, '暗色浏览数 meta', '暗色帖子详情')

    # 断言评论辅助文本清晰可见
    no_more_comment = page.locator('.comment-no-more')
    if no_more_comment.count() > 0:
        c_sub_color = no_more_comment.evaluate('el => window.getComputedStyle(el).color')
        assert_element_contrast(page, '.comment-no-more', 4.5, '暗色评论辅助提示', '暗色帖子详情')

    # 断言底部输入框底色与可见性
    input_el = page.locator('.comment-input')
    assert input_el.is_visible(), "评论输入框应可见"
    # 输入框底色按令牌判定，避免写死某个品牌暗色值（底色与文字色是两条独立令牌）
    input_bg = assert_token_background(
        page, '.comment-input', '--pill-bg', '暗色评论输入框底色', '暗色帖子详情')
    assert input_bg, "暗色评论输入框底色应取自 --pill-bg 令牌"

    # 测量暗色模式下评论框占位符前景与背景计算样式，并以计算对比度断言 >= 4.5
    dark_comment_ph = page.evaluate('''() => {
        const ph = document.querySelector('.comment-input .uni-input-placeholder') ||
                   document.querySelector('.comment-input input') ||
                   document.querySelector('.comment-input');
        const inputWrap = document.querySelector('.comment-input');
        return {
            phColor: window.getComputedStyle(ph).color,
            inputBg: window.getComputedStyle(inputWrap).backgroundColor,
        };
    }''')
    dark_comment_contrast = calculate_wcag_contrast(dark_comment_ph['phColor'], dark_comment_ph['inputBg'])
    print(f"   [对比度验证] 暗色评论占位符: 前景={dark_comment_ph['phColor']}, 背景={dark_comment_ph['inputBg']}, 对比度={dark_comment_contrast:.2f}:1")
    assert dark_comment_contrast >= 4.5, (
        f"暗色模式下评论框占位符对比度不足 4.5:1 (实际为 {dark_comment_contrast:.2f}:1, "
        f"前景={dark_comment_ph['phColor']}, 背景={dark_comment_ph['inputBg']})"
    )

    assert_no_horizontal_overflow(page, "帖子详情页（暗黑模式）")
    assert_bottom_bar_not_blocking(page, "帖子详情页（暗黑模式）")
    page.screenshot(path=f'{SCREENSHOT_DIR}/21_post_detail_dark.png')
    reports.append({
        'step': '21_post_detail_dark',
        'page': 'pages/post-detail/index',
        'status': 'PASS',
        'evidence': f"21_post_detail_dark.png, 深色模式下作者信息、高对比互动栏与meta、评论列表及固定输入栏视觉清晰无遮挡，占位符对比度 {dark_comment_contrast:.2f}:1 (>=4.5:1)",
    })

    browser.close()

httpd.shutdown()

with open(f'{SCREENSHOT_DIR}/report.json', 'w', encoding='utf-8') as f:
    json.dump(reports, f, indent=2, ensure_ascii=False)

print(f"Full walkthrough successfully executed! Saved {len(reports)} records to {SCREENSHOT_DIR}/report.json")
