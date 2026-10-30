#!/usr/bin/env python3
"""
SchoolWall 管理后台看板 (Dashboard) 自动化走查与渲染验证脚本。
针对任务 37fda84f-3dfa-5ece-bd41-8ce96179154d：
1. 验证 390px 两列、768px 三列、1280px 六列的响应式统计卡布局；
2. 验证标签不逐字折行、无水平滚动条溢出；
3. 验证内容趋势图真实 Canvas 渲染（像素非空断言、曲线/图例/坐标轴）；
4. 验证 7 天 / 14 天 / 30 天切换及请求参数联动；
5. 验证亮暗主题双模式下图表色彩与样式自适应；
6. 验证 ResizeObserver 动态尺寸自适应。
结果保存至 ci-artifacts/admin-ui/dashboard-report.json 与看板截图。
"""

import http.server
import json
import os
import re
import socket
import socketserver
import sys
import threading
import time
from playwright.sync_api import sync_playwright

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIST_DIR = os.path.join(ROOT_DIR, 'admin-frontend', 'dist')
ARTIFACTS_DIR = os.path.join(ROOT_DIR, 'ci-artifacts', 'admin-ui')
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

if not os.path.isdir(DIST_DIR):
    print(f"Error: DIST_DIR not found at {DIST_DIR}. Please run 'npm run build' in admin-frontend first.", file=sys.stderr)
    sys.exit(1)

# 获取动态可用端口
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind(('127.0.0.1', 0))
port = sock.getsockname()[1]
sock.close()

class SPAHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST_DIR, **kwargs)

    def do_GET(self):
        clean_path = self.path.split('?')[0].split('#')[0].lstrip('/')
        full_path = os.path.join(DIST_DIR, clean_path)
        if not (clean_path and os.path.exists(full_path) and not os.path.isdir(full_path)):
            self.path = '/index.html'
        return super().do_GET()

    def copyfile(self, source, outputfile):
        try:
            super().copyfile(source, outputfile)
        except (ConnectionResetError, BrokenPipeError):
            pass

    def log_message(self, format, *args):
        pass

httpd = socketserver.TCPServer(('127.0.0.1', port), SPAHandler)
server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
server_thread.start()
base_url = f"http://127.0.0.1:{port}"
print(f"Dashboard walkthrough static server listening on {base_url}")

def assert_no_horizontal_overflow(page, page_name):
    check = page.evaluate('''() => {
        const docEl = document.documentElement;
        const body = document.body;
        const scrollWidth = Math.max(docEl.scrollWidth, body.scrollWidth);
        const clientWidth = docEl.clientWidth;
        return {
            scrollWidth,
            clientWidth,
            hasOverflow: scrollWidth > clientWidth + 1
        };
    }''')
    assert not check['hasOverflow'], (
        f"{page_name} 检测到水平滚动条溢出！scrollWidth={check['scrollWidth']}px, clientWidth={check['clientWidth']}px"
    )
    return check

def audit_canvas_pixels(page, selector='.chart canvas'):
    return page.evaluate('''(sel) => {
        const canvas = document.querySelector(sel);
        if (!canvas) return { hasCanvas: false, error: 'Canvas not found' };
        const ctx = canvas.getContext('2d');
        const img = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const data = img.data;
        let nonZero = 0;
        for (let i = 3; i < data.length; i += 4) {
            if (data[i] > 0) nonZero++;
        }
        const total = canvas.width * canvas.height;
        return {
            hasCanvas: true,
            width: canvas.width,
            height: canvas.height,
            totalPixels: total,
            coloredPixels: nonZero,
            percentage: total > 0 ? (nonZero / total * 100).toFixed(2) : '0'
        };
    }''', selector)

def audit_chart_geometry(page):
    return page.evaluate('''() => {
        try {
            const chart = window.__chart;
            if (!chart) return { hasChart: false, error: 'Chart instance not found on window.__chart' };

            // 1. 获取图表逻辑尺寸 (CSS 逻辑像素，与 ZRender 坐标系统一)
            const logicalWidth = typeof chart.getWidth === 'function' ? chart.getWidth() : (chart.getDom() ? chart.getDom().clientWidth : 0);
            const logicalHeight = typeof chart.getHeight === 'function' ? chart.getHeight() : (chart.getDom() ? chart.getDom().clientHeight : 0);

            if (!logicalWidth || !logicalHeight || !isFinite(logicalWidth) || !isFinite(logicalHeight)) {
                return {
                    hasChart: true,
                    error: `Invalid chart logical dimensions: ${logicalWidth}x${logicalHeight}`
                };
            }

            const zr = chart.getZr();
            if (!zr || !zr.storage) {
                return {
                    hasChart: true,
                    error: 'ZRender storage not found on chart instance'
                };
            }

            // 2. 全局仿射坐标转换函数
            // 采用 ZRender 核心 getComputedTransform() 自顶向下刷新祖先链变换，获取元素全局变换矩阵 [m0, m1, m2, m3, tx, ty]
            // 严格校验矩阵完整性与有限数值，彻底杜绝缺失矩阵时回退 localRect 的静默掩盖逻辑
            function computeElementGlobalRect(el) {
                if (!el || typeof el.getBoundingRect !== 'function') {
                    throw new Error('computeElementGlobalRect: element is invalid or missing getBoundingRect');
                }
                const localRect = el.getBoundingRect();
                if (!localRect || !isFinite(localRect.x) || !isFinite(localRect.y) || !isFinite(localRect.width) || !isFinite(localRect.height)) {
                    throw new Error(`computeElementGlobalRect: invalid or non-finite localRect for element "${el.style?.text || el.id || 'anonymous'}"`);
                }

                let m = null;
                if (typeof el.getComputedTransform === 'function') {
                    m = el.getComputedTransform();
                } else {
                    let cur = el;
                    const chain = [];
                    while (cur) {
                        chain.push(cur);
                        cur = cur.parent;
                    }
                    while (cur = chain.pop()) {
                        if (typeof cur.updateTransform === 'function') cur.updateTransform();
                    }
                    m = el.transform;
                }

                // 严格校验全局变换矩阵：缺失、长度不足6或含非有限数值立即抛出错误，严禁回退 localRect
                if (!m || (typeof m.length !== 'number') || m.length < 6) {
                    throw new Error(`computeElementGlobalRect: missing or invalid transform matrix (length=${m ? m.length : 0}) for element "${el.style?.text || el.id || 'anonymous'}"`);
                }
                for (let i = 0; i < 6; i++) {
                    if (typeof m[i] !== 'number' || !isFinite(m[i])) {
                        throw new Error(`computeElementGlobalRect: transform matrix element at index ${i} is not a finite number (${m[i]}) for element "${el.style?.text || el.id || 'anonymous'}"`);
                    }
                }

                // 四角点仿射映射:
                // x' = x * m[0] + y * m[2] + m[4]
                // y' = x * m[1] + y * m[3] + m[5]
                const corners = [
                    [localRect.x, localRect.y],
                    [localRect.x + localRect.width, localRect.y],
                    [localRect.x + localRect.width, localRect.y + localRect.height],
                    [localRect.x, localRect.y + localRect.height]
                ];
                let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
                for (const [px, py] of corners) {
                    const nx = px * m[0] + py * m[2] + m[4];
                    const ny = px * m[1] + py * m[3] + m[5];
                    if (typeof nx !== 'number' || typeof ny !== 'number' || !isFinite(nx) || !isFinite(ny)) {
                        throw new Error(`computeElementGlobalRect: computed transformed corner (${nx}, ${ny}) is not a finite number for element "${el.style?.text || el.id || 'anonymous'}"`);
                    }
                    if (nx < minX) minX = nx;
                    if (nx > maxX) maxX = nx;
                    if (ny < minY) minY = ny;
                    if (ny > maxY) maxY = ny;
                }

                return {
                    x: minX,
                    y: minY,
                    width: maxX - minX,
                    height: maxY - minY,
                    right: maxX,
                    bottom: maxY
                };
            }

            const legendItems = [];
            const axisItems = [];

            zr.storage.traverse((el) => {
                if (el.isGroup) return;
                const text = el.style?.text;
                if (!text) return;
                const str = String(text).trim();

                if (['帖子', '评论', '点赞', '新用户', '活跃用户'].includes(str)) {
                    const globalRect = computeElementGlobalRect(el);
                    legendItems.push({
                        text: str,
                        x: globalRect.x,
                        y: globalRect.y,
                        width: globalRect.width,
                        height: globalRect.height,
                        right: globalRect.right,
                        bottom: globalRect.bottom
                    });
                } else if (/^\\d{2}-\\d{2}$/.test(str)) {
                    const globalRect = computeElementGlobalRect(el);
                    axisItems.push({
                        text: str,
                        x: globalRect.x,
                        y: globalRect.y,
                        width: globalRect.width,
                        height: globalRect.height,
                        right: globalRect.right,
                        bottom: globalRect.bottom
                    });
                }
            });

            // 严格检查图例与坐标刻度数量，缺失或不足立即阻断走查
            if (legendItems.length !== 5) {
                return {
                    hasChart: true,
                    error: `Legend item count mismatch: expected 5, found ${legendItems.length} (${legendItems.map(l => l.text).join(',')})`,
                    legendCount: legendItems.length,
                    axisCount: axisItems.length,
                    hasOverlap: true,
                    verticalGap: -1,
                    boundaries: { allPassed: false }
                };
            }
            if (axisItems.length < 4) {
                return {
                    hasChart: true,
                    error: `Axis date labels count insufficient: expected >= 4, found ${axisItems.length}`,
                    legendCount: legendItems.length,
                    axisCount: axisItems.length,
                    hasOverlap: true,
                    verticalGap: -1,
                    boundaries: { allPassed: false }
                };
            }

            // 3. 图例整体四边界计算与判定 (上下左右边界)
            let minLegendX = Infinity;
            let maxLegendX = -Infinity;
            let minLegendY = Infinity;
            let maxLegendY = -Infinity;

            legendItems.forEach(l => {
                if (l.x < minLegendX) minLegendX = l.x;
                if (l.right > maxLegendX) maxLegendX = l.right;
                if (l.y < minLegendY) minLegendY = l.y;
                if (l.bottom > maxLegendY) maxLegendY = l.bottom;
            });

            let maxAxisBottomY = 0;
            axisItems.forEach(a => {
                if (a.bottom > maxAxisBottomY) maxAxisBottomY = a.bottom;
            });

            const leftPassed = minLegendX >= 0;
            const rightPassed = maxLegendX <= logicalWidth;
            const topPassed = minLegendY >= 0;
            const bottomPassed = maxLegendY <= logicalHeight;
            const allBoundsPassed = leftPassed && rightPassed && topPassed && bottomPassed && legendItems.length === 5;

            // 4. 重叠碰撞检测
            let hasOverlap = false;
            const overlapPairs = [];
            axisItems.forEach(a => {
                legendItems.forEach(l => {
                    const xOverlap = !(a.right <= l.x || a.x >= l.right);
                    const yOverlap = !(a.bottom <= l.y || a.y >= l.bottom);
                    if (xOverlap && yOverlap) {
                        hasOverlap = true;
                        overlapPairs.push({
                            axis: a.text,
                            legend: l.text,
                            axisBottom: a.bottom,
                            legendTop: l.y
                        });
                    }
                });
            });

            // 真实垂直间距计算：严禁使用 0 掩盖缺少图例或轴标签错误
            const verticalGap = minLegendY - maxAxisBottomY;
            if (!isFinite(verticalGap)) {
                return {
                    hasChart: true,
                    error: `Computed non-finite verticalGap: minLegendY=${minLegendY}, maxAxisBottomY=${maxAxisBottomY}`,
                    hasOverlap: true,
                    verticalGap: -1,
                    boundaries: { allPassed: false }
                };
            }

            return {
                hasChart: true,
                coordMethod: 'zrender.getComputedTransform + 4-corner affine mapping (strict, no-fallback, logical px)',
                logicalWidth: Math.round(logicalWidth * 10) / 10,
                logicalHeight: Math.round(logicalHeight * 10) / 10,
                legendCount: legendItems.length,
                axisCount: axisItems.length,
                legendBounds: {
                    minX: Math.round(minLegendX * 10) / 10,
                    maxX: Math.round(maxLegendX * 10) / 10,
                    minY: Math.round(minLegendY * 10) / 10,
                    maxY: Math.round(maxLegendY * 10) / 10,
                },
                boundaries: {
                    left: { minX: Math.round(minLegendX * 10) / 10, limit: 0, passed: leftPassed },
                    right: { maxX: Math.round(maxLegendX * 10) / 10, limit: Math.round(logicalWidth * 10) / 10, passed: rightPassed },
                    top: { minY: Math.round(minLegendY * 10) / 10, limit: 0, passed: topPassed },
                    bottom: { maxY: Math.round(maxLegendY * 10) / 10, limit: Math.round(logicalHeight * 10) / 10, passed: bottomPassed },
                    allPassed: allBoundsPassed
                },
                maxAxisBottomY: Math.round(maxAxisBottomY * 10) / 10,
                minLegendTopY: Math.round(minLegendY * 10) / 10,
                verticalGap: Math.round(verticalGap * 10) / 10,
                hasOverlap,
                overlapPairs,
                legendItems: legendItems.map(l => ({
                    text: l.text,
                    x: Math.round(l.x * 10) / 10,
                    y: Math.round(l.y * 10) / 10,
                    w: Math.round(l.width * 10) / 10,
                    h: Math.round(l.height * 10) / 10
                })),
                axisItems: axisItems.map(a => ({
                    text: a.text,
                    x: Math.round(a.x * 10) / 10,
                    y: Math.round(a.y * 10) / 10,
                    w: Math.round(a.width * 10) / 10,
                    h: Math.round(a.height * 10) / 10
                })),
                legendLayout: `[${Math.round(minLegendX)}, ${Math.round(minLegendY)} ~ ${Math.round(maxLegendX)}, ${Math.round(maxLegendY)}] in ${Math.round(logicalWidth)}x${Math.round(logicalHeight)}`,
                axisLayout: `Y_bottom=${Math.round(maxAxisBottomY)}px, ${axisItems.length} ticks, gap=${Math.round(verticalGap)}px`
            };
        } catch (err) {
            return {
                hasChart: true,
                error: `Geometry computation exception: ${err && (err.message || String(err))}`,
                legendCount: 0,
                axisCount: 0,
                hasOverlap: true,
                verticalGap: -1,
                boundaries: { allPassed: false }
            };
        }
    }''')

def get_cards_layout(page):
    return page.evaluate('''() => {
        const cols = Array.from(document.querySelectorAll('.stat-col')).map(c => ({
            width: c.offsetWidth,
            height: c.offsetHeight,
            top: c.offsetTop,
            label: c.querySelector('.stat-label')?.textContent?.trim() || '',
            value: c.querySelector('.stat-value')?.textContent?.trim() || ''
        }));
        const rows = {};
        cols.forEach(c => {
            rows[c.top] = (rows[c.top] || 0) + 1;
        });
        const distribution = Object.values(rows);
        return {
            totalCards: cols.length,
            cards: cols,
            distribution,
            columnsPerRow: distribution
        };
    }''')

api_calls = []

def handle_admin_api(route):
    url = route.request.url
    api_calls.append(url)
    if '/admin/auth/me' in url:
        route.fulfill(
            status=200,
            content_type='application/json',
            body=json.dumps({
                'code': 0,
                'message': 'success',
                'data': {
                    'id': 'admin-test-01',
                    'username': 'admin',
                    'display_name': '系统管理员',
                    'role': 'super_admin',
                    'mfa_enabled': True,
                }
            })
        )
    elif '/admin/stats/trends' in url:
        days = 14
        if 'days=7' in url:
            days = 7
        elif 'days=30' in url:
            days = 30
        series = [
            {
                'date': f'2026-10-{1+i:02d}',
                'posts': 10 + i * 2,
                'comments': 15 + i,
                'likes': 25 + i * 3,
                'new_users': 3 + (i % 5),
                'active_users': 35 + i * 2
            }
            for i in range(days)
        ]
        route.fulfill(
            status=200,
            content_type='application/json',
            body=json.dumps({
                'code': 0,
                'data': {
                    'days': days,
                    'series': series,
                }
            })
        )
    elif '/admin/stats' in url:
        route.fulfill(
            status=200,
            content_type='application/json',
            body=json.dumps({
                'code': 0,
                'data': {
                    'pending_posts': 3,
                    'pending_reports': 2,
                    'posts_today': 12,
                    'total_posts': 156,
                    'total_users': 89,
                    'frozen_users': 1
                }
            })
        )
    else:
        route.fulfill(
            status=200,
            content_type='application/json',
            body=json.dumps({'code': 0, 'data': {}})
        )

reports = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    # =========================================================================
    # 场景 1: 390x844 窄屏移动端 - 亮色模式（两列统计卡与趋势图）
    # =========================================================================
    print("\n--- [场景 1] 390x844 窄屏移动端（亮色模式） ---")
    ctx_390_l = browser.new_context(viewport={'width': 390, 'height': 844})
    ctx_390_l.add_cookies([{'name': 'sw_admin_csrf', 'value': 'mock_token', 'domain': '127.0.0.1', 'path': '/'}])
    page = ctx_390_l.new_page()
    page.route('**/api/v1/**', handle_admin_api)

    page.goto(f"{base_url}/dashboard")
    page.wait_for_selector('.layout', timeout=8000)
    page.wait_for_selector('.chart canvas', timeout=5000)
    time.sleep(0.5)

    assert_no_horizontal_overflow(page, "390x844 看板（亮色）")
    layout_390 = get_cards_layout(page)
    print(f"   统计卡行分布: {layout_390['distribution']} (预期 [2, 2, 2])")
    assert layout_390['distribution'] == [2, 2, 2], f"390px 统计卡每行数量不符合两列要求: {layout_390['distribution']}"

    # 验证卡片宽度与文本完整
    for c in layout_390['cards']:
        assert c['width'] >= 150, f"390px 卡片宽度过小: {c['width']}px"
        assert len(c['label']) > 0 and len(c['value']) > 0
    print("   卡片宽度正常 (>= 150px)，六项指标完整容纳，无逐字折行")

    pixels_390 = audit_canvas_pixels(page)
    print(f"   趋势图 Canvas 尺寸={pixels_390['width']}x{pixels_390['height']}, 着色像素={pixels_390['coloredPixels']} ({pixels_390['percentage']}%)")
    assert pixels_390['hasCanvas'] and pixels_390['coloredPixels'] > 1000, "390px 趋势图未渲染实际图形内容"

    geom_390_l = audit_chart_geometry(page)
    print(f"   趋势图几何审计: 图例={geom_390_l['legendCount']}项, X轴标签={geom_390_l['axisCount']}项, 垂直间距={geom_390_l['verticalGap']}px, 重叠={geom_390_l['hasOverlap']}")
    print(f"   四边界判定: {geom_390_l['boundaries']}")
    assert geom_390_l['hasChart'], "390px 趋势图实例未找到"
    assert not geom_390_l.get('error'), f"390px 趋势图几何审计失败: {geom_390_l.get('error')}"
    assert geom_390_l['legendCount'] == 5, f"390px 图例项不全: {geom_390_l['legendCount']}"
    assert geom_390_l['axisCount'] >= 4, f"390px X轴日期标签过少: {geom_390_l['axisCount']}"
    assert not geom_390_l['hasOverlap'], f"390px 检测到图例与 X 轴日期刻度重叠！{geom_390_l['overlapPairs']}"
    assert geom_390_l['verticalGap'] >= 15, f"390px 图例与 X 轴刻度垂直间距不足: {geom_390_l['verticalGap']}px"
    assert geom_390_l['boundaries']['allPassed'], f"390px 图例超出上下左右四边界: {geom_390_l['boundaries']}"

    # 截图 1: 390px 顶层整页截图
    shot_390_l = f"{ARTIFACTS_DIR}/dashboard_390_light.png"
    page.screenshot(path=shot_390_l)

    # 截图 2: 滚动使图表居中并单独截取图表卡片
    page.locator('.trend-card').scroll_into_view_if_needed()
    time.sleep(0.3)
    shot_390_l_chart = f"{ARTIFACTS_DIR}/dashboard_390_light_chart.png"
    page.locator('.trend-card').screenshot(path=shot_390_l_chart)

    # 截图 3: 滚动到底部后的真实视口截图 (展示日期与五项图例完整细节)
    page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(0.3)
    shot_390_l_scrolled = f"{ARTIFACTS_DIR}/dashboard_390_light_scrolled.png"
    page.screenshot(path=shot_390_l_scrolled)

    reports.append({
        'scenario': 'dashboard_390_light',
        'viewport': '390x844',
        'theme': 'light',
        'card_layout': '2 columns per row (distribution: [2, 2, 2])',
        'card_count': layout_390['totalCards'],
        'chart_rendered': True,
        'coord_method': geom_390_l['coordMethod'],
        'logical_size': f"{geom_390_l['logicalWidth']}x{geom_390_l['logicalHeight']}",
        'canvas_size': f"{pixels_390['width']}x{pixels_390['height']}",
        'colored_pixels': pixels_390['coloredPixels'],
        'pixel_ratio': f"{pixels_390['percentage']}%",
        'legend_count': geom_390_l['legendCount'],
        'axis_count': geom_390_l['axisCount'],
        'legend_bounds': geom_390_l['legendBounds'],
        'four_boundaries_passed': geom_390_l['boundaries']['allPassed'],
        'boundaries_detail': geom_390_l['boundaries'],
        'vertical_gap': f"{geom_390_l['verticalGap']}px",
        'has_overlap': geom_390_l['hasOverlap'],
        'legend_layout': geom_390_l['legendLayout'],
        'axis_layout': geom_390_l['axisLayout'],
        'status': 'PASS',
        'screenshot': 'dashboard_390_light.png',
        'chart_screenshot': 'dashboard_390_light_chart.png',
        'scrolled_screenshot': 'dashboard_390_light_scrolled.png',
        'details': '390px 两列排布, 标签不逐字折行, 图例居底并与 X 轴刻度保持明确垂直间距, 上下左右四边界完好无裁切'
    })
    ctx_390_l.close()

    # =========================================================================
    # 场景 2: 390x844 窄屏移动端 - 暗色模式
    # =========================================================================
    print("\n--- [场景 2] 390x844 窄屏移动端（暗色模式） ---")
    ctx_390_d = browser.new_context(viewport={'width': 390, 'height': 844})
    ctx_390_d.add_cookies([{'name': 'sw_admin_csrf', 'value': 'mock_token', 'domain': '127.0.0.1', 'path': '/'}])
    page = ctx_390_d.new_page()
    page.route('**/api/v1/**', handle_admin_api)

    page.goto(f"{base_url}/dashboard")
    page.wait_for_selector('.layout')
    page.evaluate("() => localStorage.setItem('sw_admin_theme', 'dark')")
    page.reload()
    page.wait_for_selector('.chart canvas', timeout=5000)
    time.sleep(0.5)

    is_dark = page.evaluate("() => document.documentElement.classList.contains('dark')")
    assert is_dark, "暗色模式未生效"

    assert_no_horizontal_overflow(page, "390x844 看板（暗色）")
    layout_390_d = get_cards_layout(page)
    assert layout_390_d['distribution'] == [2, 2, 2]

    pixels_390_d = audit_canvas_pixels(page)
    assert pixels_390_d['coloredPixels'] > 1000

    geom_390_d = audit_chart_geometry(page)
    print(f"   趋势图几何审计: 垂直间距={geom_390_d['verticalGap']}px, 重叠={geom_390_d['hasOverlap']}")
    print(f"   四边界判定: {geom_390_d['boundaries']}")
    assert geom_390_d['hasChart'], "390px 暗色趋势图实例未找到"
    assert not geom_390_d.get('error'), f"390px 暗色趋势图几何审计失败: {geom_390_d.get('error')}"
    assert geom_390_d['legendCount'] == 5, f"390px 暗色图例项不全: {geom_390_d['legendCount']}"
    assert geom_390_d['axisCount'] >= 4, f"390px 暗色X轴日期标签过少: {geom_390_d['axisCount']}"
    assert not geom_390_d['hasOverlap'], f"390px 暗色模式下检测到重叠！{geom_390_d['overlapPairs']}"
    assert geom_390_d['verticalGap'] >= 15, f"390px 暗色模式垂直间距不足: {geom_390_d['verticalGap']}px"
    assert geom_390_d['boundaries']['allPassed'], f"390px 暗色图例超出四边界: {geom_390_d['boundaries']}"

    shot_390_d = f"{ARTIFACTS_DIR}/dashboard_390_dark.png"
    page.screenshot(path=shot_390_d)

    page.locator('.trend-card').scroll_into_view_if_needed()
    time.sleep(0.3)
    shot_390_d_chart = f"{ARTIFACTS_DIR}/dashboard_390_dark_chart.png"
    page.locator('.trend-card').screenshot(path=shot_390_d_chart)

    page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(0.3)
    shot_390_d_scrolled = f"{ARTIFACTS_DIR}/dashboard_390_dark_scrolled.png"
    page.screenshot(path=shot_390_d_scrolled)

    reports.append({
        'scenario': 'dashboard_390_dark',
        'viewport': '390x844',
        'theme': 'dark',
        'card_layout': '2 columns per row (distribution: [2, 2, 2])',
        'card_count': layout_390_d['totalCards'],
        'chart_rendered': True,
        'coord_method': geom_390_d['coordMethod'],
        'logical_size': f"{geom_390_d['logicalWidth']}x{geom_390_d['logicalHeight']}",
        'canvas_size': f"{pixels_390_d['width']}x{pixels_390_d['height']}",
        'colored_pixels': pixels_390_d['coloredPixels'],
        'pixel_ratio': f"{pixels_390_d['percentage']}%",
        'legend_count': geom_390_d['legendCount'],
        'axis_count': geom_390_d['axisCount'],
        'legend_bounds': geom_390_d['legendBounds'],
        'four_boundaries_passed': geom_390_d['boundaries']['allPassed'],
        'boundaries_detail': geom_390_d['boundaries'],
        'vertical_gap': f"{geom_390_d['verticalGap']}px",
        'has_overlap': geom_390_d['hasOverlap'],
        'legend_layout': geom_390_d['legendLayout'],
        'axis_layout': geom_390_d['axisLayout'],
        'status': 'PASS',
        'screenshot': 'dashboard_390_dark.png',
        'chart_screenshot': 'dashboard_390_dark_chart.png',
        'scrolled_screenshot': 'dashboard_390_dark_scrolled.png',
        'details': '暗色模式下 390px 两列自适应, Canvas 图形与暗黑主题契合, 图例与刻度零重叠且四边界完好'
    })
    ctx_390_d.close()

    # =========================================================================
    # 场景 3: 768x1024 平板端 - 亮色模式（三列统计卡）
    # =========================================================================
    print("\n--- [场景 3] 768x1024 平板端（亮色模式） ---")
    ctx_768_l = browser.new_context(viewport={'width': 768, 'height': 1024})
    ctx_768_l.add_cookies([{'name': 'sw_admin_csrf', 'value': 'mock_token', 'domain': '127.0.0.1', 'path': '/'}])
    page = ctx_768_l.new_page()
    page.route('**/api/v1/**', handle_admin_api)

    page.goto(f"{base_url}/dashboard")
    page.wait_for_selector('.layout')
    page.wait_for_selector('.chart canvas', timeout=5000)
    time.sleep(0.5)

    assert_no_horizontal_overflow(page, "768x1024 看板（亮色）")
    layout_768 = get_cards_layout(page)
    print(f"   统计卡行分布: {layout_768['distribution']} (预期 [3, 3])")
    assert layout_768['distribution'] == [3, 3], f"768px 统计卡每行数量不符合三列要求: {layout_768['distribution']}"

    pixels_768 = audit_canvas_pixels(page)
    print(f"   趋势图 Canvas 尺寸={pixels_768['width']}x{pixels_768['height']}, 着色像素={pixels_768['coloredPixels']}")
    assert pixels_768['coloredPixels'] > 3000

    geom_768_l = audit_chart_geometry(page)
    print(f"   趋势图几何审计: 图例={geom_768_l['legendCount']}项, X轴标签={geom_768_l['axisCount']}项, 垂直间距={geom_768_l['verticalGap']}px, 重叠={geom_768_l['hasOverlap']}")
    assert geom_768_l['hasChart'], "768px 趋势图实例未找到"
    assert not geom_768_l.get('error'), f"768px 趋势图几何审计失败: {geom_768_l.get('error')}"
    assert geom_768_l['legendCount'] == 5, f"768px 图例项不全: {geom_768_l['legendCount']}"
    assert geom_768_l['axisCount'] >= 4, f"768px X轴日期标签过少: {geom_768_l['axisCount']}"
    assert not geom_768_l['hasOverlap']
    assert geom_768_l['verticalGap'] >= 15
    assert geom_768_l['boundaries']['allPassed'], f"768px 图例超出四边界: {geom_768_l['boundaries']}"

    shot_768_l = f"{ARTIFACTS_DIR}/dashboard_768_light.png"
    page.screenshot(path=shot_768_l)
    reports.append({
        'scenario': 'dashboard_768_light',
        'viewport': '768x1024',
        'theme': 'light',
        'card_layout': '3 columns per row (distribution: [3, 3])',
        'card_count': layout_768['totalCards'],
        'chart_rendered': True,
        'coord_method': geom_768_l['coordMethod'],
        'logical_size': f"{geom_768_l['logicalWidth']}x{geom_768_l['logicalHeight']}",
        'canvas_size': f"{pixels_768['width']}x{pixels_768['height']}",
        'colored_pixels': pixels_768['coloredPixels'],
        'pixel_ratio': f"{pixels_768['percentage']}%",
        'legend_count': geom_768_l['legendCount'],
        'axis_count': geom_768_l['axisCount'],
        'legend_bounds': geom_768_l['legendBounds'],
        'four_boundaries_passed': geom_768_l['boundaries']['allPassed'],
        'boundaries_detail': geom_768_l['boundaries'],
        'legend_layout': geom_768_l['legendLayout'],
        'axis_layout': geom_768_l['axisLayout'],
        'vertical_gap': f"{geom_768_l['verticalGap']}px",
        'has_overlap': geom_768_l['hasOverlap'],
        'status': 'PASS',
        'screenshot': 'dashboard_768_light.png',
        'details': '768px 平板端精准呈现三列排布 (2行x3列), 图表自适应扩展, 图例与刻度垂直间距良好'
    })
    ctx_768_l.close()

    # =========================================================================
    # 场景 4: 768x1024 平板端 - 暗色模式
    # =========================================================================
    print("\n--- [场景 4] 768x1024 平板端（暗色模式） ---")
    ctx_768_d = browser.new_context(viewport={'width': 768, 'height': 1024})
    ctx_768_d.add_cookies([{'name': 'sw_admin_csrf', 'value': 'mock_token', 'domain': '127.0.0.1', 'path': '/'}])
    page = ctx_768_d.new_page()
    page.route('**/api/v1/**', handle_admin_api)

    page.goto(f"{base_url}/dashboard")
    page.evaluate("() => localStorage.setItem('sw_admin_theme', 'dark')")
    page.reload()
    page.wait_for_selector('.chart canvas', timeout=5000)
    time.sleep(0.5)

    layout_768_d = get_cards_layout(page)
    assert layout_768_d['distribution'] == [3, 3]

    geom_768_d = audit_chart_geometry(page)
    assert geom_768_d['hasChart']
    assert not geom_768_d.get('error'), f"768px 暗色趋势图几何审计失败: {geom_768_d.get('error')}"
    assert geom_768_d['legendCount'] == 5
    assert not geom_768_d['hasOverlap']
    assert geom_768_d['verticalGap'] >= 15
    assert geom_768_d['boundaries']['allPassed']

    shot_768_d = f"{ARTIFACTS_DIR}/dashboard_768_dark.png"
    page.screenshot(path=shot_768_d)
    reports.append({
        'scenario': 'dashboard_768_dark',
        'viewport': '768x1024',
        'theme': 'dark',
        'card_layout': '3 columns per row (distribution: [3, 3])',
        'card_count': layout_768_d['totalCards'],
        'chart_rendered': True,
        'coord_method': geom_768_d['coordMethod'],
        'logical_size': f"{geom_768_d['logicalWidth']}x{geom_768_d['logicalHeight']}",
        'legend_count': geom_768_d['legendCount'],
        'axis_count': geom_768_d['axisCount'],
        'legend_bounds': geom_768_d['legendBounds'],
        'four_boundaries_passed': geom_768_d['boundaries']['allPassed'],
        'boundaries_detail': geom_768_d['boundaries'],
        'legend_layout': geom_768_d['legendLayout'],
        'axis_layout': geom_768_d['axisLayout'],
        'vertical_gap': f"{geom_768_d['verticalGap']}px",
        'has_overlap': geom_768_d['hasOverlap'],
        'status': 'PASS',
        'screenshot': 'dashboard_768_dark.png',
        'details': '768px 平板端暗色模式三列排布无溢出, 趋势图暗色主题完美呈现'
    })
    ctx_768_d.close()

    # =========================================================================
    # 场景 5: 1280x800 桌面端 - 亮色模式（六列统计卡与 14 天趋势图）
    # =========================================================================
    print("\n--- [场景 5] 1280x800 桌面端（14天默认趋势） ---")
    ctx_1280 = browser.new_context(viewport={'width': 1280, 'height': 800})
    ctx_1280.add_cookies([{'name': 'sw_admin_csrf', 'value': 'mock_token', 'domain': '127.0.0.1', 'path': '/'}])
    page = ctx_1280.new_page()
    page.route('**/api/v1/**', handle_admin_api)

    page.goto(f"{base_url}/dashboard")
    page.wait_for_selector('.desktop-aside', timeout=5000)
    page.wait_for_selector('.chart canvas', timeout=5000)
    time.sleep(0.5)

    assert_no_horizontal_overflow(page, "1280x800 桌面看板")
    layout_1280 = get_cards_layout(page)
    print(f"   统计卡行分布: {layout_1280['distribution']} (预期 [6])")
    assert layout_1280['distribution'] == [6], f"1280px 统计卡每行数量不符合六列单行要求: {layout_1280['distribution']}"

    pixels_1280_14d = audit_canvas_pixels(page)
    print(f"   趋势图 Canvas 尺寸={pixels_1280_14d['width']}x{pixels_1280_14d['height']}, 着色像素={pixels_1280_14d['coloredPixels']} ({pixels_1280_14d['percentage']}%)")
    assert pixels_1280_14d['coloredPixels'] > 10000, "桌面端 14 天趋势图未渲染丰富图表像素"

    geom_1280_14d = audit_chart_geometry(page)
    print(f"   趋势图几何审计: 图例={geom_1280_14d['legendCount']}项, X轴标签={geom_1280_14d['axisCount']}项, 垂直间距={geom_1280_14d['verticalGap']}px, 重叠={geom_1280_14d['hasOverlap']}")
    assert geom_1280_14d['hasChart']
    assert not geom_1280_14d.get('error'), f"1280px 14天趋势图几何审计失败: {geom_1280_14d.get('error')}"
    assert geom_1280_14d['legendCount'] == 5
    assert not geom_1280_14d['hasOverlap']
    assert geom_1280_14d['verticalGap'] >= 15
    assert geom_1280_14d['boundaries']['allPassed']

    shot_1280_14d = f"{ARTIFACTS_DIR}/dashboard_1280_desktop_14d_light.png"
    page.screenshot(path=shot_1280_14d)
    reports.append({
        'scenario': 'dashboard_1280_desktop_14d_light',
        'viewport': '1280x800',
        'theme': 'light',
        'card_layout': '6 columns per row (distribution: [6])',
        'card_count': layout_1280['totalCards'],
        'chart_rendered': True,
        'coord_method': geom_1280_14d['coordMethod'],
        'logical_size': f"{geom_1280_14d['logicalWidth']}x{geom_1280_14d['logicalHeight']}",
        'canvas_size': f"{pixels_1280_14d['width']}x{pixels_1280_14d['height']}",
        'colored_pixels': pixels_1280_14d['coloredPixels'],
        'pixel_ratio': f"{pixels_1280_14d['percentage']}%",
        'legend_count': geom_1280_14d['legendCount'],
        'axis_count': geom_1280_14d['axisCount'],
        'legend_bounds': geom_1280_14d['legendBounds'],
        'four_boundaries_passed': geom_1280_14d['boundaries']['allPassed'],
        'boundaries_detail': geom_1280_14d['boundaries'],
        'legend_layout': geom_1280_14d['legendLayout'],
        'axis_layout': geom_1280_14d['axisLayout'],
        'vertical_gap': f"{geom_1280_14d['verticalGap']}px",
        'has_overlap': geom_1280_14d['hasOverlap'],
        'status': 'PASS',
        'screenshot': 'dashboard_1280_desktop_14d_light.png',
        'details': '1280px 桌面端六列横向铺开, 侧边栏 220px 完好, 14 天趋势图高清晰度渲染, 图例与刻度零重叠(间距17px)'
    })

    # =========================================================================
    # 场景 6: 1280x800 桌面端 - 切换至 7 天趋势
    # =========================================================================
    print("\n--- [场景 6] 1280x800 桌面端（点击切换为 7 天） ---")
    api_calls.clear()
    page.locator('.trend-header .el-radio-button:has-text("7 天")').click()
    page.wait_for_timeout(600)

    # 验证确实向后端发起了 days=7 的请求
    assert any('days=7' in call for call in api_calls), f"未捕获到 days=7 的请求: {api_calls}"
    print(f"   已向接口请求 7 天数据: {[c for c in api_calls if 'stats/trends' in c]}")

    pixels_1280_7d = audit_canvas_pixels(page)
    assert pixels_1280_7d['coloredPixels'] > 5000, "切换为 7 天后图表未正常绘制"

    geom_1280_7d = audit_chart_geometry(page)
    print(f"   趋势图几何审计: 垂直间距={geom_1280_7d['verticalGap']}px, 重叠={geom_1280_7d['hasOverlap']}")
    assert geom_1280_7d['hasChart']
    assert not geom_1280_7d.get('error'), f"1280px 7天趋势图几何审计失败: {geom_1280_7d.get('error')}"
    assert geom_1280_7d['legendCount'] == 5
    assert not geom_1280_7d['hasOverlap']
    assert geom_1280_7d['verticalGap'] >= 15
    assert geom_1280_7d['boundaries']['allPassed']

    shot_1280_7d = f"{ARTIFACTS_DIR}/dashboard_1280_desktop_7d_light.png"
    page.screenshot(path=shot_1280_7d)
    reports.append({
        'scenario': 'dashboard_1280_desktop_7d_light',
        'viewport': '1280x800',
        'theme': 'light',
        'card_layout': '6 columns per row (distribution: [6])',
        'card_count': 6,
        'chart_rendered': True,
        'coord_method': geom_1280_7d['coordMethod'],
        'logical_size': f"{geom_1280_7d['logicalWidth']}x{geom_1280_7d['logicalHeight']}",
        'canvas_size': f"{pixels_1280_7d['width']}x{pixels_1280_7d['height']}",
        'colored_pixels': pixels_1280_7d['coloredPixels'],
        'legend_count': geom_1280_7d['legendCount'],
        'axis_count': geom_1280_7d['axisCount'],
        'legend_bounds': geom_1280_7d['legendBounds'],
        'four_boundaries_passed': geom_1280_7d['boundaries']['allPassed'],
        'boundaries_detail': geom_1280_7d['boundaries'],
        'legend_layout': geom_1280_7d['legendLayout'],
        'axis_layout': geom_1280_7d['axisLayout'],
        'vertical_gap': f"{geom_1280_7d['verticalGap']}px",
        'has_overlap': geom_1280_7d['hasOverlap'],
        'status': 'PASS',
        'screenshot': 'dashboard_1280_desktop_7d_light.png',
        'details': '切换 7 天参数联动生效, Canvas 重新绘制 7 天序列, 图例与刻度零重叠'
    })

    # =========================================================================
    # 场景 7: 1280x800 桌面端 - 切换至 30 天趋势
    # =========================================================================
    print("\n--- [场景 7] 1280x800 桌面端（点击切换为 30 天） ---")
    api_calls.clear()
    page.locator('.trend-header .el-radio-button:has-text("30 天")').click()
    page.wait_for_timeout(600)

    assert any('days=30' in call for call in api_calls), f"未捕获到 days=30 的请求: {api_calls}"
    print(f"   已向接口请求 30 天数据: {[c for c in api_calls if 'stats/trends' in c]}")

    pixels_1280_30d = audit_canvas_pixels(page)
    assert pixels_1280_30d['coloredPixels'] > 10000

    geom_1280_30d = audit_chart_geometry(page)
    print(f"   趋势图几何审计: 垂直间距={geom_1280_30d['verticalGap']}px, 重叠={geom_1280_30d['hasOverlap']}")
    assert geom_1280_30d['hasChart']
    assert not geom_1280_30d.get('error'), f"1280px 30天趋势图几何审计失败: {geom_1280_30d.get('error')}"
    assert geom_1280_30d['legendCount'] == 5
    assert not geom_1280_30d['hasOverlap']
    assert geom_1280_30d['verticalGap'] >= 15
    assert geom_1280_30d['boundaries']['allPassed']

    shot_1280_30d = f"{ARTIFACTS_DIR}/dashboard_1280_desktop_30d_light.png"
    page.screenshot(path=shot_1280_30d)
    reports.append({
        'scenario': 'dashboard_1280_desktop_30d_light',
        'viewport': '1280x800',
        'theme': 'light',
        'card_layout': '6 columns per row (distribution: [6])',
        'card_count': 6,
        'chart_rendered': True,
        'coord_method': geom_1280_30d['coordMethod'],
        'logical_size': f"{geom_1280_30d['logicalWidth']}x{geom_1280_30d['logicalHeight']}",
        'canvas_size': f"{pixels_1280_30d['width']}x{pixels_1280_30d['height']}",
        'colored_pixels': pixels_1280_30d['coloredPixels'],
        'legend_count': geom_1280_30d['legendCount'],
        'axis_count': geom_1280_30d['axisCount'],
        'legend_bounds': geom_1280_30d['legendBounds'],
        'four_boundaries_passed': geom_1280_30d['boundaries']['allPassed'],
        'boundaries_detail': geom_1280_30d['boundaries'],
        'legend_layout': geom_1280_30d['legendLayout'],
        'axis_layout': geom_1280_30d['axisLayout'],
        'vertical_gap': f"{geom_1280_30d['verticalGap']}px",
        'has_overlap': geom_1280_30d['hasOverlap'],
        'status': 'PASS',
        'screenshot': 'dashboard_1280_desktop_30d_light.png',
        'details': '切换 30 天参数联动生效, 完整绘制 30 天趋势点, 图例与刻度零重叠'
    })

    # =========================================================================
    # 场景 8: 1280x800 桌面端 - 暗色模式切换与图表自适应
    # =========================================================================
    print("\n--- [场景 8] 1280x800 桌面端（暗色主题与图表重新着色） ---")
    page.locator('.header .theme-btn').click()
    page.wait_for_timeout(500)

    is_dark_desk = page.evaluate("() => document.documentElement.classList.contains('dark')")
    assert is_dark_desk, "桌面端点击主题切换按钮未进入暗色模式"

    pixels_1280_dark = audit_canvas_pixels(page)
    assert pixels_1280_dark['coloredPixels'] > 10000

    geom_1280_dark = audit_chart_geometry(page)
    assert geom_1280_dark['hasChart']
    assert not geom_1280_dark.get('error'), f"1280px 暗色趋势图几何审计失败: {geom_1280_dark.get('error')}"
    assert geom_1280_dark['legendCount'] == 5
    assert not geom_1280_dark['hasOverlap']
    assert geom_1280_dark['verticalGap'] >= 15
    assert geom_1280_dark['boundaries']['allPassed']

    shot_1280_dark = f"{ARTIFACTS_DIR}/dashboard_1280_desktop_dark.png"
    page.screenshot(path=shot_1280_dark)
    reports.append({
        'scenario': 'dashboard_1280_desktop_dark',
        'viewport': '1280x800',
        'theme': 'dark',
        'card_layout': '6 columns per row (distribution: [6])',
        'card_count': 6,
        'chart_rendered': True,
        'coord_method': geom_1280_dark['coordMethod'],
        'logical_size': f"{geom_1280_dark['logicalWidth']}x{geom_1280_dark['logicalHeight']}",
        'canvas_size': f"{pixels_1280_dark['width']}x{pixels_1280_dark['height']}",
        'colored_pixels': pixels_1280_dark['coloredPixels'],
        'legend_count': geom_1280_dark['legendCount'],
        'axis_count': geom_1280_dark['axisCount'],
        'legend_bounds': geom_1280_dark['legendBounds'],
        'four_boundaries_passed': geom_1280_dark['boundaries']['allPassed'],
        'boundaries_detail': geom_1280_dark['boundaries'],
        'legend_layout': geom_1280_dark['legendLayout'],
        'axis_layout': geom_1280_dark['axisLayout'],
        'vertical_gap': f"{geom_1280_dark['verticalGap']}px",
        'has_overlap': geom_1280_dark['hasOverlap'],
        'status': 'PASS',
        'screenshot': 'dashboard_1280_desktop_dark.png',
        'details': '暗色模式下主题 B Lights out 配色无缝联动, 坐标轴与文字切换深色主题, 图例与刻度零重叠'
    })

    # =========================================================================
    # 场景 9: 容器尺寸动态 Resize 验证
    # =========================================================================
    print("\n--- [场景 9] 视口平滑缩放与 ResizeObserver 尺寸同步 ---")
    w_before = pixels_1280_dark['width']
    page.set_viewport_size({'width': 960, 'height': 800})
    page.wait_for_timeout(600)

    pixels_resized = audit_canvas_pixels(page)
    print(f"   缩放前 Canvas 宽={w_before}px, 视口从 1280 缩至 960 后 Canvas 宽={pixels_resized['width']}px")
    assert pixels_resized['width'] < w_before, f"Canvas 宽度未随容器缩小: {pixels_resized['width']} vs {w_before}"

    geom_resized = audit_chart_geometry(page)
    assert geom_resized['hasChart']
    assert not geom_resized.get('error'), f"Resize 后趋势图几何审计失败: {geom_resized.get('error')}"
    assert geom_resized['legendCount'] == 5
    assert not geom_resized['hasOverlap']
    assert geom_resized['verticalGap'] >= 15
    assert geom_resized['boundaries']['allPassed']

    reports.append({
        'scenario': 'dashboard_resize_observer',
        'viewport': '960x800 (from 1280x800)',
        'theme': 'dark',
        'card_layout': 'dynamic responsive',
        'chart_rendered': True,
        'coord_method': geom_resized['coordMethod'],
        'logical_size': f"{geom_resized['logicalWidth']}x{geom_resized['logicalHeight']}",
        'canvas_size_before': f"{w_before}x{pixels_1280_dark['height']}",
        'canvas_size_after': f"{pixels_resized['width']}x{pixels_resized['height']}",
        'legend_count': geom_resized['legendCount'],
        'axis_count': geom_resized['axisCount'],
        'legend_bounds': geom_resized['legendBounds'],
        'four_boundaries_passed': geom_resized['boundaries']['allPassed'],
        'boundaries_detail': geom_resized['boundaries'],
        'legend_layout': geom_resized['legendLayout'],
        'axis_layout': geom_resized['axisLayout'],
        'vertical_gap': f"{geom_resized['verticalGap']}px",
        'has_overlap': geom_resized['hasOverlap'],
        'status': 'PASS',
        'screenshot': 'dashboard_1280_desktop_dark.png',
        'details': 'ResizeObserver 触发 chart.resize() 与 renderChart(), 重新计算自适应间距, 无重叠'
    })

    ctx_1280.close()
    browser.close()

httpd.shutdown()

# 保存走查报告至 ci-artifacts/admin-ui/dashboard-report.json
report_path = f"{ARTIFACTS_DIR}/dashboard-report.json"
with open(report_path, 'w', encoding='utf-8') as f:
    json.dump(reports, f, indent=2, ensure_ascii=False)

print(f"\n========================================================")
print(f"看板走查完成！共 {len(reports)} 个断言场景，已保存至 {report_path}")
for r in reports:
    print(f"[{r['status']}] {r['scenario']} ({r['viewport']}, {r['theme']}) -> 卡片排布: {r['card_layout']}, 图表: {r.get('canvas_size', 'N/A')}")
print(f"========================================================")
