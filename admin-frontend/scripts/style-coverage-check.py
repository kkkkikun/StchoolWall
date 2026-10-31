#!/usr/bin/env python3
"""管理台 Element Plus 样式覆盖检查。

按需引入（unplugin-vue-components / unplugin-auto-import）之后，组件样式由
构建期注入，有两类容易漏掉、且肉眼难发现的问题：

1. **样式没注入**：某个 el-* 组件被用在模板里，但构建产物里没有它的样式，
   页面照样渲染，只是长得不像 Element Plus（对话框没边框、表格没斑马纹）。
2. **样式落错 chunk**：服务型 API（ElMessage / ElMessageBox）的样式被注入到
   某个懒加载视图的 CSS chunk，而真正使用它的 request.ts 在主 chunk 里，
   首屏弹提示时就没有样式。

本脚本做静态核对：模板里用到的组件，其根类必须出现在构建产物 CSS 中；
服务型 API 的样式必须出现在**主 chunk** 的 CSS 中。

用法：python3 scripts/style-coverage-check.py
退出码非零 -> 有组件缺样式。
"""

import glob
import json
import os
import pathlib
import re
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = os.path.join(ROOT_DIR, 'admin-frontend', 'src')
DIST_DIR = os.path.join(ROOT_DIR, 'admin-frontend', 'dist')
ASSETS_DIR = os.path.join(DIST_DIR, 'assets')

# 这些组件没有自己的根类样式（纯结构组件，或样式由父组件/其他文件承载）
NO_OWN_STYLE = {
    'container', 'aside', 'header', 'main', 'footer',
    'table-column', 'descriptions-item', 'dropdown-item', 'option',
    'radio-group', 'checkbox-group', 'menu-item', 'sub-menu', 'form-item',
}
# 组件名 -> 产物 CSS 里实际使用的根类
CLASS_ALIAS = {
    'date-picker': 'el-date-editor',
    'time-picker': 'el-date-editor',
    'radio-button': 'el-radio-button',
    'checkbox-button': 'el-checkbox-button',
    'input-number': 'el-input-number',
    'scrollbar': 'el-scrollbar',
    'space': 'el-space',
}

# 服务型 API：request.ts 在主 chunk 里用到 ElMessage，样式必须进主 chunk。
# 用各组件独有的深层选择器做判据（`.el-message` 这类根类名在别的样式里也会出现，
# 会造成误判通过）。
MAIN_CHUNK_SERVICES = {
    'el-message': '.el-message__content',
    'el-message-box': '.el-message-box__btns',
}


def collect_used_components():
    used = set()
    for path in pathlib.Path(SRC_DIR).rglob('*.vue'):
        text = path.read_text(encoding='utf-8', errors='ignore')
        used |= set(re.findall(r'<el-([a-z0-9-]+)', text))
    return used


def css_text(pattern):
    files = sorted(glob.glob(os.path.join(ASSETS_DIR, pattern)))
    return '\n'.join(pathlib.Path(f).read_text(encoding='utf-8') for f in files), files


def main():
    if not os.path.isdir(ASSETS_DIR):
        print(f'Error: 未找到构建产物 {ASSETS_DIR}，请先 npm run build', file=sys.stderr)
        return 2

    all_css, css_files = css_text('*.css')
    main_css, main_files = css_text('index-*.css')

    used = collect_used_components()
    findings = []

    for name in sorted(used):
        if name in NO_OWN_STYLE:
            continue
        root_class = CLASS_ALIAS.get(name, f'el-{name}')
        if root_class not in all_css:
            findings.append(f'组件 <el-{name}> 在模板中使用，但产物 CSS 里找不到 {root_class}')

    for name, marker in MAIN_CHUNK_SERVICES.items():
        if marker not in main_css:
            findings.append(
                f'服务型 API {name} 的样式不在主 chunk CSS 里'
                f'（缺 {marker}；主 chunk CSS: {[os.path.basename(f) for f in main_files]}）')

    report = {
        'components_used': len(used),
        'css_files': len(css_files),
        'main_chunk_css': [os.path.basename(f) for f in main_files],
        'findings': findings,
        'status': 'FAIL' if findings else 'PASS',
    }
    out = os.path.join(ROOT_DIR, 'ci-artifacts', 'admin-ui', 'style-coverage.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    if findings:
        print('[失败] Element Plus 样式覆盖不完整：')
        for f in findings:
            print('   -', f)
        print(f'报告: {out}')
        return 1

    print(f'[通过] {len(used)} 个 Element Plus 组件样式齐全，主 chunk 服务型样式就位 '
          f'（{len(css_files)} 个 CSS 文件）')
    print(f'报告: {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
