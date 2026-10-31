#!/usr/bin/env python3
"""管理台产物体积预算守卫。

Element Plus 改按需引入、echarts 改按需注册之后，管理台首屏与看板体积都降了
一大截。但这两项优化**没有任何东西守着**：谁把 `app.use(ElementPlus)` 或
`import('echarts')` 写回去，体积会静默涨回去，CI 一点反应都没有。

本脚本把体积基线入库，超出预算即非零退出。

用法：python3 scripts/bundle-budget-check.py [--update]
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
ADMIN_DIR = os.path.join(ROOT_DIR, 'admin-frontend')
DIST_DIR = os.path.join(ADMIN_DIR, 'dist')
ASSETS_DIR = os.path.join(DIST_DIR, 'assets')
BASELINE = os.path.join(ADMIN_DIR, 'bundle-baseline.json')
REPORT = os.path.join(ROOT_DIR, 'ci-artifacts', 'admin-ui', 'bundle-budget.json')

DEFAULT_TOLERANCE = 0.10


def gzip_size(path):
    with open(path, 'rb') as fh:
        return len(gzip.compress(fh.read(), 9))


def measure():
    if not os.path.isdir(ASSETS_DIR):
        print(f'Error: 未找到构建产物 {ASSETS_DIR}，请先 npm run build:admin', file=sys.stderr)
        return None

    assets = pathlib.Path(ASSETS_DIR)
    js = sorted(assets.glob('*.js'))
    css = sorted(assets.glob('*.css'))

    index = pathlib.Path(DIST_DIR) / 'index.html'
    refs = re.findall(r'(?:src|href)="([^"]+)"', index.read_text(encoding='utf-8')) if index.is_file() else []
    entry_js = [assets / pathlib.Path(r).name for r in refs if r.endswith('.js')]
    entry_css = [assets / pathlib.Path(r).name for r in refs if r.endswith('.css')]

    def total(paths):
        return sum(gzip_size(p) for p in paths if p.is_file())

    echarts = sorted(assets.glob('echarts-*.js'))

    return {
        'main_chunk_js_gzip': total(entry_js),
        'main_chunk_css_gzip': total(entry_css),
        'echarts_chunk_gzip': sum(gzip_size(p) for p in echarts),
        'total_js_gzip': sum(gzip_size(p) for p in js),
        'total_css_gzip': sum(gzip_size(p) for p in css),
        'largest_js_gzip': max((gzip_size(p) for p in js), default=0),
        'js_count': len(js),
        'css_count': len(css),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--update', action='store_true', help='刷新基线文件')
    args = ap.parse_args()

    current = measure()
    if current is None:
        return 2

    if args.update:
        baseline = {
            'updated_at': __import__('datetime').date.today().isoformat(),
            'tolerance': DEFAULT_TOLERANCE,
            'note': '体积为 gzip -9 后的字节数；echarts_chunk 守住按需注册的成果',
            'bundle': current,
        }
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
        'findings': findings,
        'status': 'FAIL' if findings else 'PASS',
    }
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    if findings:
        print('[失败] 管理台产物体积超出基线预算：')
        for f in findings:
            print('   -', f)
        print(f'报告: {REPORT}')
        return 1

    print('[通过] 管理台产物体积在基线预算内：'
          f'首屏 JS {current["main_chunk_js_gzip"] / 1024:.1f}KB gzip、'
          f'echarts 块 {current["echarts_chunk_gzip"] / 1024:.1f}KB gzip、'
          f'全量 JS {current["total_js_gzip"] / 1024:.1f}KB gzip')
    print(f'报告: {REPORT}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
