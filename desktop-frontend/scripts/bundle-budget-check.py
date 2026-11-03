#!/usr/bin/env python3
"""电脑端产物体积预算守卫。

学生端有 `frontend/scripts/perf-budget-check.py`（基线 `frontend/perf-baseline.json`），
管理台有 `admin-frontend/scripts/bundle-budget-check.py`（基线 `admin-frontend/bundle-baseline.json`），
电脑端此前没有体积基线 —— 依赖升级带来的主 chunk 膨胀不会被当场抓住。

本脚本把体积基线入库，超出预算即非零退出。体积是确定性的（同样的代码必然得到同样的数字），
因此可以严格卡阈值；学生端与管理台都用 gzip -9 的字节数，本脚本保持同一口径。

用法：
    python3 scripts/bundle-budget-check.py            # 门禁：超出预算即 exit 1
    python3 scripts/bundle-budget-check.py --update   # 刷新基线（需人工确认后提交）

退出码非零 -> 体积超出预算。
"""

import argparse
import datetime
import gzip
import json
import os
import pathlib
import re
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DESKTOP_DIR = os.path.join(ROOT_DIR, 'desktop-frontend')
DIST_DIR = os.path.join(DESKTOP_DIR, 'dist')
ASSETS_DIR = os.path.join(DIST_DIR, 'assets')
BASELINE = os.path.join(DESKTOP_DIR, 'bundle-baseline.json')
REPORT = os.path.join(ROOT_DIR, 'ci-artifacts', 'desktop-ui', 'bundle-budget.json')

# 默认允许的体积增长幅度（依赖升级带来的正常波动），与管理台、学生端一致
DEFAULT_TOLERANCE = 0.10


def gzip_size(path):
    """按 gzip -9 计算压缩后体积，与发布时的传输体积一致。"""
    with open(path, 'rb') as fh:
        return len(gzip.compress(fh.read(), 9))


def raw_size(path):
    return os.path.getsize(path)


def entry_assets():
    """index.html 直接引用的资源（首屏入口）。"""
    index = pathlib.Path(DIST_DIR) / 'index.html'
    if not index.is_file():
        return []
    text = index.read_text(encoding='utf-8')
    return re.findall(r'(?:src|href)="([^"]+)"', text)


def measure():
    """统计产物体积指标（字节；raw 与 gzip 两套口径）。"""
    if not os.path.isdir(ASSETS_DIR):
        print(f'Error: 未找到构建产物 {ASSETS_DIR}，请先 npm run build:desktop', file=sys.stderr)
        return None

    assets = pathlib.Path(ASSETS_DIR)
    js = sorted(assets.glob('*.js'))
    css = sorted(assets.glob('*.css'))

    refs = entry_assets()
    entry_js = [assets / os.path.basename(ref) for ref in refs if ref.endswith('.js')]
    entry_css = [assets / os.path.basename(ref) for ref in refs if ref.endswith('.css')]

    def total(paths, size):
        return sum(size(p) for p in paths if p.is_file())

    dist_raw = 0
    for root, _dirs, files in os.walk(DIST_DIR):
        for name in files:
            dist_raw += os.path.getsize(os.path.join(root, name))

    return {
        'main_chunk_js_raw': total(entry_js, raw_size),
        'main_chunk_js_gzip': total(entry_js, gzip_size),
        'main_chunk_css_raw': total(entry_css, raw_size),
        'main_chunk_css_gzip': total(entry_css, gzip_size),
        'total_js_raw': total(js, raw_size),
        'total_js_gzip': total(js, gzip_size),
        'total_css_raw': total(css, raw_size),
        'total_css_gzip': total(css, gzip_size),
        'largest_js_raw': max((raw_size(p) for p in js), default=0),
        'largest_js_gzip': max((gzip_size(p) for p in js), default=0),
        'dist_raw_bytes': dist_raw,
        'js_count': len(js),
        'css_count': len(css),
    }


def compare(current, baseline_bundle, tolerance):
    """逐项比对基线，返回超出预算的条目说明。"""
    findings = []
    for key, cur in current.items():
        if key not in baseline_bundle:
            continue
        base = baseline_bundle[key]
        limit = base * (1 + tolerance)
        if cur > limit:
            findings.append(
                f'{key}: {cur} 字节，超过基线 {base} 的 {tolerance:.0%} 上限 {int(limit)}'
                f'（+{cur - base} 字节）')
    return findings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--update', action='store_true', help='刷新基线文件')
    args = ap.parse_args()

    current = measure()
    if current is None:
        return 2

    if args.update:
        baseline = {
            'updated_at': datetime.date.today().isoformat(),
            'tolerance': DEFAULT_TOLERANCE,
            'note': '体积为字节数；gzip 口径为 gzip -9，与学生端、管理台同一算法；'
                    'raw 口径为磁盘原始大小',
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

    findings = compare(current, base_bundle, tolerance)

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
        print('[失败] 电脑端产物体积超出基线预算：')
        for f in findings:
            print('   -', f)
        print(f'报告: {REPORT}')
        return 1

    print('[通过] 电脑端产物体积在基线预算内：'
          f'主 chunk {current["main_chunk_js_raw"] / 1024:.1f}KB raw / '
          f'{current["main_chunk_js_gzip"] / 1024:.1f}KB gzip、'
          f'全量产物 {current["dist_raw_bytes"] / 1024:.1f}KB raw')
    print(f'报告: {REPORT}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
