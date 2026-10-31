#!/usr/bin/env python3
"""图标注册表一致性守卫。

守护 `openspec/specs/frontend-ui/spec.md` 的「图标体系单一来源」：

1. **磁盘 ↔ 注册表一一对应**：磁盘上每个 .svg 都登记在 `src/utils/icons.ts`，
   注册表里每条路径都真实存在于磁盘（不多、不少）。
2. **源码不手写路径**：`src/` 下除注册表本身外，不得出现 `/static/icons/...`
   字面量 —— 否则生成器一旦调整路径，这些引用就静默 404。
3. **注册表可解析**：路径必须形如 `/static/icons/<group>/<file>.svg`。

为什么需要：图标几何由 `frontend/scripts/gen_icons.py` 统一生成，页面引用
必须跟着注册表走，否则「唯一来源」只是一句口号。

用法：python3 scripts/icon-consistency-check.py
退出码非零 -> 有不一致。
"""

import json
import os
import pathlib
import re
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = os.path.join(ROOT_DIR, 'frontend', 'src')
ICON_ROOT = os.path.join(SRC_DIR, 'static', 'icons')
REGISTRY = os.path.join(SRC_DIR, 'utils', 'icons.ts')

PATH_LITERAL = re.compile(r"/static/icons/[A-Za-z0-9_\-/]+\.svg")
VALID_PATH = re.compile(r"^/static/icons/[a-z\-]+/[a-z0-9\-]+\.svg$")

# 注册表里允许同一路径挂在多个语义名下（别名），因此按集合比对
# 顶层：'semantic-name': '/static/icons/...'
BASE_ENTRY = re.compile(r"^  '([^']+)': '(/static/icons/[^']+)',$", re.M)
# tone 层：'semantic-name': { 'primary': '/static/icons/...', ... }
TONE_ENTRY = re.compile(r"^  '([^']+)': \{ (.*) \},$", re.M)
TONE_PAIR = re.compile(r"'([^']+)': '(/static/icons/[^']+)'")


def registry_paths():
    """返回 (路径集合, {语义名: 路径})。"""
    text = pathlib.Path(REGISTRY).read_text(encoding='utf-8')
    mapping = dict(BASE_ENTRY.findall(text))
    for name, inner in TONE_ENTRY.findall(text):
        for tone, path in TONE_PAIR.findall(inner):
            mapping[f'{name}#{tone}'] = path
    return set(mapping.values()), mapping


def disk_paths():
    """返回磁盘上所有 .svg 相对 icons/ 的路径集合（与注册表同一形式）。"""
    out = set()
    for p in pathlib.Path(ICON_ROOT).rglob('*.svg'):
        out.add(p.relative_to(ICON_ROOT).as_posix())
    return out


def to_rel(path):
    """'/static/icons/common/x.svg' -> 'common/x.svg'"""
    return path.split('/static/icons/', 1)[-1]


def hand_written_refs():
    """源码里手写的图标路径（排除注册表本身）。"""
    hits = []
    for p in sorted(pathlib.Path(SRC_DIR).rglob('*')):
        if not p.is_file() or p.suffix not in ('.vue', '.ts', '.js'):
            continue
        if p.resolve() == pathlib.Path(REGISTRY).resolve():
            continue
        text = p.read_text(encoding='utf-8', errors='ignore')
        for i, line in enumerate(text.splitlines(), 1):
            for m in PATH_LITERAL.finditer(line):
                hits.append(f'{p.relative_to(SRC_DIR).as_posix()}:{i} -> {m.group(0)}')
    return hits


def main():
    findings = []

    if not os.path.isfile(REGISTRY):
        print(f'Error: 未找到注册表 {REGISTRY}', file=sys.stderr)
        return 2
    if not os.path.isdir(ICON_ROOT):
        print(f'Error: 未找到图标目录 {ICON_ROOT}', file=sys.stderr)
        return 2

    reg_set, mapping = registry_paths()
    disk_set = disk_paths()
    reg_rel = {to_rel(p) for p in reg_set}

    # 1. 磁盘 ↔ 注册表一一对应
    for p in sorted(disk_set - reg_rel):
        findings.append(f'磁盘有 {p} 但未登记进注册表')
    for p in sorted(reg_rel - disk_set):
        findings.append(f'注册表登记了 {p} 但磁盘上不存在该文件')

    # 2. 注册表路径格式
    for name, path in sorted(mapping.items()):
        if not VALID_PATH.match(path):
            findings.append(f'注册表语义名 {name} 的路径格式非法：{path}')

    # 3. 源码不手写路径
    for hit in hand_written_refs():
        findings.append(f'源码里手写了图标路径（应走注册表）：{hit}')

    report = {
        'registry_entries': len(mapping),
        'registry_paths': len(reg_set),
        'disk_svgs': len(disk_set),
        'hand_written_refs': len(hand_written_refs()),
        'findings': findings,
        'status': 'FAIL' if findings else 'PASS',
    }
    out = os.path.join(ROOT_DIR, 'ci-artifacts', 'ui-walkthrough', 'icon-consistency.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    if findings:
        print('[失败] 图标注册表不一致：')
        for f in findings:
            print('   -', f)
        print(f'报告: {out}')
        return 1

    print(f'[通过] {len(disk_set)} 个 SVG 与注册表一一对应（{len(mapping)} 个语义名），'
          f'源码无手写图标路径')
    print(f'报告: {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
