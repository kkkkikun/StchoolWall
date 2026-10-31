#!/usr/bin/env python3
"""前端性能基线与门禁。

性能退化目前只能靠人肉看 —— 这个脚本把基线入库，并自动判定是否退化。

判定分两层：

1. **产物体积（硬门禁）**：从 H5 构建产物统计首屏与全量的 JS / CSS 体积，
   与仓库里的基线 `frontend/perf-baseline.json` 比对。体积是**确定性**的，
   同样的代码必然得到同样的数字，所以可以严格卡阈值。超过基线
   `tolerance`（默认 +10%）即非零退出 —— 依赖升级引入的体积膨胀会被当场抓住。
2. **运行时指标（只记录不拦截）**：FCP / DOMContentLoaded / LCP 受 CI runner
   负载影响很大，硬卡会造成误报式的随机失败，因此只记录到基线文件旁边，
   供人工横向比较。真正会卡住回归的是第 1 层。

用法：
    python3 scripts/perf-budget-check.py                # 只跑产物体积门禁
    python3 scripts/perf-budget-check.py --base-url URL # 附带运行时指标采集
    python3 scripts/perf-budget-check.py --update       # 刷新基线（需人工确认后提交）

退出码非零 -> 体积超出预算。
"""

import argparse
import gzip
import json
import os
import pathlib
import re
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FRONTEND_DIR = os.path.join(ROOT_DIR, 'frontend')
DIST_DIR = os.path.join(FRONTEND_DIR, 'dist', 'build', 'h5')
BASELINE = os.path.join(FRONTEND_DIR, 'perf-baseline.json')
REPORT = os.path.join(ROOT_DIR, 'ci-artifacts', 'ui-walkthrough', 'perf-budget.json')

# 默认允许的体积增长幅度（依赖升级带来的正常波动）
DEFAULT_TOLERANCE = 0.10


def gzip_size(path):
    """按 gzip -9 计算压缩后体积，与发布时的传输体积一致。"""
    with open(path, 'rb') as fh:
        return len(gzip.compress(fh.read(), 9))


def entry_assets():
    """index.html 直接引用的资源（首屏入口）。"""
    index = pathlib.Path(DIST_DIR) / 'index.html'
    if not index.is_file():
        return []
    text = index.read_text(encoding='utf-8')
    return re.findall(r'(?:src|href)="(/assets/[^"]+)"', text)


def measure():
    """统计产物体积指标（字节，gzip 后）。"""
    assets = pathlib.Path(DIST_DIR) / 'assets'
    if not assets.is_dir():
        print(f'Error: 未找到构建产物 {assets}，请先 npm run build:h5', file=sys.stderr)
        return None

    js = sorted(assets.glob('*.js'))
    css = sorted(assets.glob('*.css'))

    entry = entry_assets()
    entry_js = [a for a in entry if a.endswith('.js')]
    entry_css = [a for a in entry if a.endswith('.css')]

    def total(paths):
        return sum(gzip_size(pathlib.Path(DIST_DIR) / p.lstrip('/')) for p in paths)

    def raw_total(paths):
        return sum((pathlib.Path(DIST_DIR) / p.lstrip('/')).stat().st_size for p in paths)

    largest = max((gzip_size(p) for p in js), default=0)

    return {
        'first_screen_js_gzip': total(entry_js),
        'first_screen_css_gzip': total(entry_css),
        'first_screen_total_gzip': total(entry_js) + total(entry_css),
        'total_js_gzip': sum(gzip_size(p) for p in js),
        'total_css_gzip': sum(gzip_size(p) for p in css),
        'total_raw_bytes': sum(p.stat().st_size for p in js) + sum(p.stat().st_size for p in css),
        'largest_js_gzip': largest,
        'js_count': len(js),
        'css_count': len(css),
    }


def collect_runtime(base_url, pages=('index', 'search', 'post-detail')):
    """采集运行时首屏指标（只记录，不作为门禁）。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {'error': 'playwright 未安装，跳过运行时指标采集'}

    routes = {
        'index': '/#/pages/index/index',
        'search': '/#/pages/search/index',
        'post-detail': '/#/pages/post-detail/index?id=1',
    }
    out = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=['--no-sandbox'])
            ctx = browser.new_context(viewport={'width': 390, 'height': 844})
            page = ctx.new_page()
            for name in pages:
                route = routes.get(name)
                if not route:
                    continue
                page.goto(f'{base_url}{route}', wait_until='networkidle')
                page.wait_for_timeout(600)
                m = page.evaluate("""() => {
                    const nav = performance.getEntriesByType('navigation')[0] || {};
                    const paints = {};
                    for (const p of performance.getEntriesByType('paint')) {
                        paints[p.name] = Math.round(p.startTime);
                    }
                    const lcp = performance.getEntriesByType('largest-contentful-paint');
                    return {
                        fcp: paints['first-contentful-paint'] || 0,
                        dcl: Math.round(nav.domContentLoadedEventEnd || 0),
                        load: Math.round(nav.loadEventEnd || 0),
                        lcp: lcp.length ? Math.round(lcp[lcp.length - 1].startTime) : 0,
                        resources: performance.getEntriesByType('resource').length,
                    };
                }""")
                out[name] = m
            browser.close()
    except Exception as exc:  # 运行时采集失败不应挡住体积门禁
        return {'error': f'运行时指标采集失败：{exc}'}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base-url', default='', help='可用的预览服务地址，用于采集运行时指标')
    ap.add_argument('--update', action='store_true', help='刷新基线文件')
    args = ap.parse_args()

    current = measure()
    if current is None:
        return 2

    runtime = {}
    if args.base_url:
        runtime = collect_runtime(args.base_url)

    if args.update:
        baseline = {
            'updated_at': __import__('datetime').date.today().isoformat(),
            'tolerance': DEFAULT_TOLERANCE,
            'note': '体积为 gzip -9 后的字节数；运行时指标只记录不拦截（受 runner 负载影响）',
            'bundle': current,
        }
        if runtime and 'error' not in runtime:
            baseline['runtime_observed'] = runtime
        with open(BASELINE, 'w', encoding='utf-8') as fh:
            json.dump(baseline, fh, ensure_ascii=False, indent=2)
        print(f'[已更新] 基线 -> {BASELINE}')
        for k, v in current.items():
            print(f'   {k}: {v}')
        return 0

    if not os.path.isfile(BASELINE):
        print(f'Error: 未找到基线 {BASELINE}，请先跑 --update 生成', file=sys.stderr)
        return 2

    with open(BASELINE, encoding='utf-8') as fh:
        baseline = json.load(fh)
    base_bundle = baseline.get('bundle', {})
    tolerance = baseline.get('tolerance', DEFAULT_TOLERANCE)

    findings = []
    for key, cur in current.items():
        if key not in base_bundle:
            continue
        base = base_bundle[key]
        limit = base * (1 + tolerance)
        if cur > limit:
            findings.append(
                f'{key}: {cur} 字节，超过基线 {base} 的 {tolerance:.0%} 上限 {int(limit)}'
                f'（+{cur - base} 字节）')

    report = {
        'baseline': base_bundle,
        'current': current,
        'tolerance': tolerance,
        'runtime_observed': runtime,
        'findings': findings,
        'status': 'FAIL' if findings else 'PASS',
    }
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    if findings:
        print('[失败] 前端产物体积超出基线预算：')
        for f in findings:
            print('   -', f)
        print(f'报告: {REPORT}')
        return 1

    print('[通过] 前端产物体积在基线预算内：'
          f'首屏 JS {current["first_screen_js_gzip"] / 1024:.1f}KB gzip、'
          f'全量 JS {current["total_js_gzip"] / 1024:.1f}KB gzip、'
          f'全量 CSS {current["total_css_gzip"] / 1024:.1f}KB gzip')
    if runtime and 'error' not in runtime:
        for name, m in runtime.items():
            print(f'   [参考] {name}: FCP {m["fcp"]}ms / DCL {m["dcl"]}ms / LCP {m["lcp"]}ms')
    elif runtime:
        print(f'   [参考] {runtime.get("error")}')
    print(f'报告: {REPORT}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
