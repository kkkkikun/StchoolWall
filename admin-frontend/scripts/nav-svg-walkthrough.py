#!/usr/bin/env python3
"""
SchoolWall 管理后台导航 SVG 图标专项验收脚本（独立脚本，不改动 ui-walkthrough.py）。

针对已构建的 admin-frontend/dist，用单个 Headless Chromium 顺序验证 4 个场景：
  1. 1280x800 桌面亮色  —— 18 个菜单 SVG 断言 + 主题颜色 + 激活项
  2. 1280x800 桌面暗色  —— 同上（暗色令牌）
  3. 390x844 手机亮色   —— 抽屉内 18 个 SVG + 对齐 + 滚动 + 点击「用户管理」
                           验证路由 /users、面包屑更新、抽屉自动关闭、改密/退出入口
  4. 390x844 手机暗色   —— 抽屉内 18 个 SVG + 暗色主题显示

每个 .menu-icon 必须包含真实 SVG 节点且尺寸非零、无横向溢出、
颜色经 currentColor 继承菜单文字色。任一断言失败 -> 场景记 FAIL，脚本退出码非零。

产物：
  ci-artifacts/admin-ui/nav-svg-desktop-light.png
  ci-artifacts/admin-ui/nav-svg-desktop-dark.png
  ci-artifacts/admin-ui/nav-svg-mobile-light.png
  ci-artifacts/admin-ui/nav-svg-mobile-dark.png
  ci-artifacts/admin-ui/nav-svg-mobile-light-scrolled.png（抽屉滚动到底部补充截图）
  ci-artifacts/admin-ui/nav-svg-browser-report.json

使用模拟管理员数据与本地 HTTP 服务，不访问真实后台，不读取任何凭据。
"""

import json
import os
import sys
import time
import traceback
from playwright.sync_api import sync_playwright

from walkthrough_server import create_server, route_url  # 同目录共享模块

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIST_DIR = os.path.join(ROOT_DIR, 'admin-frontend', 'dist')
ARTIFACTS_DIR = os.path.join(ROOT_DIR, 'ci-artifacts', 'admin-ui')
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

if not os.path.isdir(DIST_DIR):
    print(f"Error: DIST_DIR not found at {DIST_DIR}. Run 'npm run build' first.", file=sys.stderr)
    sys.exit(1)

# 与 AdminLayout.vue 中 menus 配置一一对应（顺序敏感）
EXPECTED_MENUS = [
    ('/dashboard', '看板'),
    ('/posts', '帖子管理'),
    ('/moderation-jobs', '人工审核'),
    ('/appeals', '申诉处理'),
    ('/moderation-records', '审核记录'),
    ('/sensitive-words', '敏感词库'),
    ('/student-verifications', '学生证认证'),
    ('/users', '用户管理'),
    ('/reports', '举报处理'),
    ('/feedback', '反馈箱'),
    ('/comments', '评论管理'),
    ('/parties', '组局管理'),
    ('/banners', '轮播广告'),
    ('/announcements', '公告群发'),
    ('/logs', '操作日志'),
    ('/admins', '管理员账号'),
    ('/tags', '标签管理'),
    ('/activities', '站内活动'),
]
MENU_COUNT = len(EXPECTED_MENUS)
assert MENU_COUNT == 18

# ---------------------------------------------------------------- 静态服务器
httpd, base_url = create_server(DIST_DIR)
print(f"Admin static server listening on {base_url}")

# ---------------------------------------------------------------- Mock API
def handle_admin_api(route):
    url = route.request.url
    if '/admin/auth/me' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps({
            'code': 0, 'message': 'success',
            'data': {'id': 'admin-test-01', 'username': 'admin', 'display_name': '系统管理员',
                     'role': 'super_admin', 'mfa_enabled': True}
        }))
    elif '/admin/stats/trends' in url:
        days = 7 if 'days=7' in url else (30 if 'days=30' in url else 14)
        series = [{'date': f'2026-10-{1+i:02d}', 'posts': 10+i, 'comments': 20+i,
                   'likes': 30+i, 'new_users': 5+i, 'active_users': 40+i} for i in range(days)]
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps({'code': 0, 'data': {'days': days, 'series': series}}))
    elif '/admin/stats' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps({
            'code': 0, 'data': {'pending_posts': 3, 'pending_reports': 2, 'posts_today': 12,
                                'total_posts': 156, 'total_users': 89, 'frozen_users': 1}}))
    elif '/api/v1/' in url or '/admin/' in url:
        route.fulfill(status=200, content_type='application/json',
                      body=json.dumps({'code': 0, 'message': 'ok', 'data': {'items': [], 'total': 0}}))
    else:
        route.continue_()

# ---------------------------------------------------------------- 断言工具
def check(condition, message):
    if not condition:
        raise AssertionError(message)

def assert_menu_svg(page, scope_selector, scenario_name):
    """对指定作用域内的 18 个菜单做 SVG 真实 DOM 断言，返回明细列表。"""
    items = page.locator(f'{scope_selector} .el-menu-item')
    check(items.count() == MENU_COUNT,
          f"{scenario_name}: 菜单项数量应为 {MENU_COUNT}，实际为 {items.count()}")

    details = []
    for i, (expected_path, expected_title) in enumerate(EXPECTED_MENUS):
        item = items.nth(i)
        # el-menu-item 的 index(path) 是 prop，不渲染为 DOM 属性；
        # 顺序+标题断言菜单配置，path 由场景 3 的实际点击跳转验证
        title = item.text_content().strip()
        check(expected_title in title,
              f"{scenario_name}: 第{i+1}项（{expected_path}）标题应含「{expected_title}」，实际为「{title}」")

        icon = item.locator('.menu-icon')
        check(icon.count() == 1, f"{scenario_name}: 第{i+1}项「{expected_title}」缺少 .menu-icon 容器")
        svg = icon.locator('svg')
        check(svg.count() == 1,
              f"{scenario_name}: 第{i+1}项「{expected_title}」的 .menu-icon 内没有真实 SVG 节点")

        box = svg.bounding_box()
        check(box is not None and box['width'] >= 14 and box['height'] >= 14,
              f"{scenario_name}: 第{i+1}项「{expected_title}」SVG 尺寸异常: {box}")

        # 图标不得横向溢出所在菜单项
        item_box = item.bounding_box()
        check(box['x'] >= item_box['x'] - 1 and box['x'] + box['width'] <= item_box['x'] + item_box['width'] + 1,
              f"{scenario_name}: 第{i+1}项「{expected_title}」SVG 横向溢出菜单项: icon={box}, item={item_box}")

        # currentColor 颜色继承：SVG 计算颜色必须与菜单项文字计算颜色一致且非透明
        colors = page.evaluate('''(el) => {
            const svg = el.querySelector('.menu-icon svg');
            const svgColor = window.getComputedStyle(svg).color;
            const itemColor = window.getComputedStyle(el).color;
            return { svgColor, itemColor };
        }''', item.element_handle())
        check('rgba(0, 0, 0, 0)' not in (colors['svgColor'],),
              f"{scenario_name}: 第{i+1}项「{expected_title}」SVG 颜色透明，继承失败")
        check(colors['svgColor'] == colors['itemColor'],
              f"{scenario_name}: 第{i+1}项「{expected_title}」SVG 颜色({colors['svgColor']})"
              f"未继承菜单文字色({colors['itemColor']})")

        details.append({'index': i + 1, 'path': expected_path, 'title': expected_title,
                        'svg': True, 'width': round(box['width'], 1), 'height': round(box['height'], 1),
                        'color': colors['svgColor']})
    return details

def assert_icon_text_alignment(page, scope_selector, scenario_name):
    """抽查首项图标与文字的垂直居中对齐（偏差 <= 3px）。"""
    m = page.evaluate('''(scope) => {
        const item = document.querySelector(scope + ' .el-menu-item');
        const svg = item.querySelector('.menu-icon svg');
        const text = item.querySelector('span:last-child');
        const s = svg.getBoundingClientRect();
        const t = text.getBoundingClientRect();
        return { iconCenter: s.top + s.height / 2, textCenter: t.top + t.height / 2 };
    }''', scope_selector)
    delta = abs(m['iconCenter'] - m['textCenter'])
    check(delta <= 3, f"{scenario_name}: 图标与文字垂直中心偏差 {delta:.1f}px (>3px)")
    return round(delta, 2)

def assert_no_horizontal_overflow(page, scenario_name):
    r = page.evaluate('''() => {
        const d = document.documentElement, b = document.body;
        return { sw: Math.max(d.scrollWidth, b.scrollWidth), cw: d.clientWidth };
    }''')
    check(r['sw'] <= r['cw'] + 1,
          f"{scenario_name}: 页面水平溢出 scrollWidth={r['sw']} > clientWidth={r['cw']}")

# ---------------------------------------------------------------- 场景执行
report = {
    'task': 'admin nav SVG icons browser acceptance',
    'date_utc': time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()),
    'base_url': base_url,
    'menu_count_expected': MENU_COUNT,
    'scenarios': [],
    'screenshots': [],
    'overall': 'PASS',
}

def record(scenario, viewport, theme, status, assertions=None, error=None, screenshots=None):
    report['scenarios'].append({
        'scenario': scenario, 'viewport': viewport, 'theme': theme,
        'status': status, 'assertions': assertions or {}, 'error': error,
        'screenshots': screenshots or [],
    })
    if screenshots:
        report['screenshots'].extend(screenshots)
    if status != 'PASS':
        report['overall'] = 'FAIL'

def new_admin_context(browser, width, height, theme):
    ctx = browser.new_context(viewport={'width': width, 'height': height})
    ctx.add_cookies([{'name': 'sw_admin_csrf', 'value': 'mock_test_csrf_token',
                      'domain': '127.0.0.1', 'path': '/'}])
    if theme == 'dark':
        ctx.add_init_script("localStorage.setItem('sw_admin_theme', 'dark')")
    page = ctx.new_page()
    page.route('**/api/v1/**', handle_admin_api)
    return ctx, page

exit_code = 0
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # ======================== 场景 1: 桌面 1280x800 亮色 ========================
        name = 'desktop-light'
        print(f"\n--- 场景 1: 1280x800 桌面亮色 ---")
        try:
            ctx, page = new_admin_context(browser, 1280, 800, 'light')
            page.goto(route_url(base_url, '/dashboard'))
            page.wait_for_selector('.desktop-aside', timeout=8000)
            page.wait_for_selector('.desktop-aside .el-menu-item .menu-icon svg', timeout=5000)
            time.sleep(0.3)

            check(page.locator('.desktop-aside').is_visible(), '桌面侧栏应可见')
            check(not page.locator('.mobile-toggle').is_visible(), '桌面端汉堡按钮应隐藏')
            is_dark = page.evaluate("() => document.documentElement.classList.contains('dark')")
            check(not is_dark, '亮色场景不应带有 dark 类')

            details = assert_menu_svg(page, '.desktop-aside', name)
            align_delta = assert_icon_text_alignment(page, '.desktop-aside', name)

            # 激活项（当前 /dashboard）样式：激活图标颜色 = 激活文字颜色
            active = page.locator('.desktop-aside .el-menu-item.is-active')
            check(active.count() == 1, f'{name}: 应恰好 1 个激活菜单项，实际 {active.count()}')
            active_colors = page.evaluate('''() => {
                const el = document.querySelector('.desktop-aside .el-menu-item.is-active');
                return { icon: window.getComputedStyle(el.querySelector('.menu-icon svg')).color,
                         text: window.getComputedStyle(el).color };
            }''')
            check(active_colors['icon'] == active_colors['text'],
                  f"{name}: 激活项图标色({active_colors['icon']}) != 文字色({active_colors['text']})")

            assert_no_horizontal_overflow(page, name)
            shot = 'nav-svg-desktop-light.png'
            page.screenshot(path=f'{ARTIFACTS_DIR}/{shot}')
            print(f"   [通过] 18 项 SVG 全部真实渲染，对齐偏差 {align_delta}px，激活项颜色一致")
            record(name, '1280x800', 'light', 'PASS',
                   assertions={'menus': details, 'align_delta_px': align_delta,
                               'active_icon_color': active_colors['icon'],
                               'hamburger_hidden': True, 'horizontal_overflow': False},
                   screenshots=[shot])
            ctx.close()
        except Exception as e:
            print(f"   [失败] {e}")
            record(name, '1280x800', 'light', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            try:
                ctx.close()
            except Exception:
                pass

        # ======================== 场景 2: 桌面 1280x800 暗色 ========================
        name = 'desktop-dark'
        print(f"\n--- 场景 2: 1280x800 桌面暗色 ---")
        try:
            ctx, page = new_admin_context(browser, 1280, 800, 'dark')
            page.goto(route_url(base_url, '/dashboard'))
            page.wait_for_selector('.desktop-aside', timeout=8000)
            page.wait_for_selector('.desktop-aside .el-menu-item .menu-icon svg', timeout=5000)
            time.sleep(0.3)

            is_dark = page.evaluate("() => document.documentElement.classList.contains('dark')")
            check(is_dark, '暗色场景 documentElement 应带 dark 类')

            details = assert_menu_svg(page, '.desktop-aside', name)
            align_delta = assert_icon_text_alignment(page, '.desktop-aside', name)
            # 暗色令牌生效：侧栏背景应与亮色不同（非纯白）
            aside_bg = page.evaluate(
                "() => window.getComputedStyle(document.querySelector('.desktop-aside')).backgroundColor")
            check(aside_bg != 'rgb(255, 255, 255)', f'{name}: 暗色侧栏背景异常: {aside_bg}')

            assert_no_horizontal_overflow(page, name)
            shot = 'nav-svg-desktop-dark.png'
            page.screenshot(path=f'{ARTIFACTS_DIR}/{shot}')
            print(f"   [通过] 暗色 18 项 SVG 渲染正常，侧栏背景 {aside_bg}，对齐偏差 {align_delta}px")
            record(name, '1280x800', 'dark', 'PASS',
                   assertions={'menus': details, 'align_delta_px': align_delta,
                               'dark_class': True, 'aside_bg': aside_bg, 'horizontal_overflow': False},
                   screenshots=[shot])
            ctx.close()
        except Exception as e:
            print(f"   [失败] {e}")
            record(name, '1280x800', 'dark', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            try:
                ctx.close()
            except Exception:
                pass

        # ======================== 场景 3: 手机 390x844 亮色 + 交互 ========================
        name = 'mobile-light'
        print(f"\n--- 场景 3: 390x844 手机亮色（含点击交互） ---")
        try:
            ctx, page = new_admin_context(browser, 390, 844, 'light')
            page.goto(route_url(base_url, '/dashboard'))
            page.wait_for_selector('.layout', timeout=8000)
            time.sleep(0.3)

            check(not page.locator('.desktop-aside').is_visible(), '窄屏桌面侧栏应隐藏')
            check(page.locator('.mobile-toggle').is_visible(), '窄屏汉堡按钮应可见')

            page.locator('.mobile-toggle').click()
            page.wait_for_selector('.drawer-content', state='visible', timeout=5000)
            page.wait_for_selector('.drawer-content .el-menu-item .menu-icon svg', timeout=5000)
            time.sleep(0.4)

            details = assert_menu_svg(page, '.drawer-content', name)
            align_delta = assert_icon_text_alignment(page, '.drawer-content', name)

            # 抽屉滚动：滚动区可滚动且能滚到底部看到最后一项
            scroll_info = page.evaluate('''() => {
                const wrap = document.querySelector('.drawer-menu-scroll .el-scrollbar__wrap');
                if (!wrap) return { found: false };
                const before = wrap.scrollTop;
                wrap.scrollTop = wrap.scrollHeight;
                return { found: true, before, after: wrap.scrollTop,
                         scrollHeight: wrap.scrollHeight, clientHeight: wrap.clientHeight };
            }''')
            check(scroll_info['found'], f'{name}: 未找到抽屉滚动容器')
            check(scroll_info['scrollHeight'] >= scroll_info['clientHeight'],
                  f"{name}: 抽屉滚动区高度异常: {scroll_info}")
            last_item = page.locator('.drawer-content .el-menu-item').nth(MENU_COUNT - 1)
            check(last_item.is_visible(), f'{name}: 滚动到底部后最后一项「站内活动」不可见')
            shot_scrolled = 'nav-svg-mobile-light-scrolled.png'
            page.screenshot(path=f'{ARTIFACTS_DIR}/{shot_scrolled}')
            page.evaluate("() => { document.querySelector('.drawer-menu-scroll .el-scrollbar__wrap').scrollTop = 0 }")
            time.sleep(0.2)

            # 改密 / 退出入口可见（不实际操作账号）
            check(page.locator('.drawer-actions button:has-text("改密")').is_visible(), '改密入口应可见')
            check(page.locator('.drawer-actions button:has-text("退出")').is_visible(), '退出入口应可见')

            shot = 'nav-svg-mobile-light.png'
            page.screenshot(path=f'{ARTIFACTS_DIR}/{shot}')

            # 点击「用户管理」-> 路由 /users、面包屑更新、抽屉关闭
            page.locator('.drawer-content .el-menu-item:has-text("用户管理")').click()
            page.wait_for_url('**/users', timeout=5000)
            time.sleep(0.6)
            check('/users' in page.url, f'{name}: 点击后 URL 应进入 /users，实际 {page.url}')
            breadcrumb = page.locator('.breadcrumb').text_content()
            check('用户管理' in breadcrumb, f'{name}: 面包屑应为「用户管理」，实际「{breadcrumb}」')
            drawer_hidden = page.evaluate('''() => {
                const el = document.querySelector('.drawer-content');
                if (!el) return true;
                return el.getBoundingClientRect().width === 0 || !el.offsetParent;
            }''')
            check(drawer_hidden, f'{name}: 点击菜单后抽屉未关闭')

            print(f"   [通过] 抽屉 18 项 SVG + 滚动 + 对齐({align_delta}px) 正常；"
                  f"点击「用户管理」跳转 {page.url}，面包屑「{breadcrumb.strip()}」，抽屉已关闭")
            record(name, '390x844', 'light', 'PASS',
                   assertions={'menus': details, 'align_delta_px': align_delta,
                               'drawer_scroll': scroll_info,
                               'pwd_entry_visible': True, 'logout_entry_visible': True,
                               'click_navigate': {'url': page.url, 'breadcrumb': breadcrumb.strip(),
                                                  'drawer_closed': True}},
                   screenshots=[shot, shot_scrolled])
            ctx.close()
        except Exception as e:
            print(f"   [失败] {e}")
            record(name, '390x844', 'light', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            try:
                ctx.close()
            except Exception:
                pass

        # ======================== 场景 4: 手机 390x844 暗色 ========================
        name = 'mobile-dark'
        print(f"\n--- 场景 4: 390x844 手机暗色 ---")
        try:
            ctx, page = new_admin_context(browser, 390, 844, 'dark')
            page.goto(route_url(base_url, '/dashboard'))
            page.wait_for_selector('.layout', timeout=8000)
            time.sleep(0.3)

            is_dark = page.evaluate("() => document.documentElement.classList.contains('dark')")
            check(is_dark, '暗色场景 documentElement 应带 dark 类')

            page.locator('.mobile-toggle').click()
            page.wait_for_selector('.drawer-content', state='visible', timeout=5000)
            page.wait_for_selector('.drawer-content .el-menu-item .menu-icon svg', timeout=5000)
            time.sleep(0.4)

            details = assert_menu_svg(page, '.drawer-content', name)
            align_delta = assert_icon_text_alignment(page, '.drawer-content', name)
            drawer_bg = page.evaluate(
                "() => window.getComputedStyle(document.querySelector('.drawer-content')).backgroundColor")
            check(drawer_bg != 'rgb(255, 255, 255)', f'{name}: 暗色抽屉背景异常: {drawer_bg}')
            check(page.locator('.drawer-actions button:has-text("改密")').is_visible(), '改密入口应可见')
            check(page.locator('.drawer-actions button:has-text("退出")').is_visible(), '退出入口应可见')

            shot = 'nav-svg-mobile-dark.png'
            page.screenshot(path=f'{ARTIFACTS_DIR}/{shot}')
            print(f"   [通过] 暗色抽屉 18 项 SVG 渲染正常，抽屉背景 {drawer_bg}，对齐偏差 {align_delta}px")
            record(name, '390x844', 'dark', 'PASS',
                   assertions={'menus': details, 'align_delta_px': align_delta,
                               'dark_class': True, 'drawer_bg': drawer_bg},
                   screenshots=[shot])
            ctx.close()
        except Exception as e:
            print(f"   [失败] {e}")
            record(name, '390x844', 'dark', 'FAIL', error=f'{e}\n{traceback.format_exc(limit=3)}')
            try:
                ctx.close()
            except Exception:
                pass

        browser.close()
except Exception as e:
    print(f"\n[致命错误] {e}", file=sys.stderr)
    report['overall'] = 'FAIL'
    report['fatal'] = f'{e}\n{traceback.format_exc(limit=3)}'
finally:
    httpd.shutdown()

report_path = f'{ARTIFACTS_DIR}/nav-svg-browser-report.json'
with open(report_path, 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print(f"\n========================================================")
passed = sum(1 for s in report['scenarios'] if s['status'] == 'PASS')
print(f"导航 SVG 验收结束: {passed}/{len(report['scenarios'])} 场景通过，总体 {report['overall']}")
print(f"报告: {report_path}")
print(f"========================================================")

if report['overall'] != 'PASS':
    sys.exit(1)
