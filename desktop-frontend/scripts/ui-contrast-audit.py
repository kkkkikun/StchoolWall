#!/usr/bin/env python3
"""电脑端深色模式与对比度客观扫描。

学生端的 `frontend/scripts/ui-contrast-audit.py` 已经把「亮/暗双模式逐页扫描」
跑通，电脑端此前只有人工目视。本脚本沿用同一套做法，但把断言收敛到**令牌**上：

- 颜色只从 `desktop-frontend/src/styles/tokens.css` 读（亮色 `:root` 与暗色 `.theme-dark`），
  断言基于令牌与实测对比度，**不写死任何色值**（换品牌、改暗色文字后断言依然成立）；
- 页面在浏览器里渲染，按祖先链合成实色层与线性渐变（取元素位置的实际 alpha），
  底色未知处按最坏情况（纯白）取下界；
- 每个可见文字元素的前景色都**反查成令牌名**再判定角色，正文角色不达标即阻断。

阻断项（任一不达标即 exit 1）：
1. 源码引用了未定义的令牌；
2. 正文令牌在页面底 / 卡片底上的对比度 < 4.5:1（亮暗两套配色都要）；
3. 白字压品牌主色 < 4.5:1，或品牌主色压亮色卡片底 < 4.5:1；
4. 品牌文字令牌、弱化文字令牌在各自底色上的对比度 < 4.5:1；
5. Element Plus 的占位符 < 4.0:1、次要文字 < 4.5:1、禁用文字 < 4.5:1；
6. 运行时扫描里**任何可见文字**（正文、品牌色文字、次要/弱化文字、其他令牌、字面量色值）
   的对比度 < 4.5:1（大字 ≥3:1），占位符 < 4.0:1。

不阻断但会记录的问题：只有照片底上的文字 —— 底色由后台下发、无法客观合成，
按最坏情况（纯白）取下界后仍不达标才记为观察项。

用法：
    cd desktop-frontend && python3 scripts/ui-contrast-audit.py
"""

import json
import pathlib
import re
import sys

ROOT_DIR = pathlib.Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / 'desktop-frontend' / 'src'
TOKENS_CSS = SRC_DIR / 'styles' / 'tokens.css'
DIST_DIR = ROOT_DIR / 'desktop-frontend' / 'dist'
ARTIFACTS_DIR = ROOT_DIR / 'ci-artifacts' / 'desktop-ui'
REPORT = ARTIFACTS_DIR / 'contrast-audit.json'

# 阈值来自 openspec/specs/frontend-ui/spec.md「文本对比度令牌化」
BODY_MIN = 4.5      # 正文
LARGE_MIN = 3.0      # 大字
PLACEHOLDER_MIN = 4.0  # 占位符

# 品牌色相关令牌：按 frontend 的既有口径单列计数
BRAND_TOKENS = ('--sw-primary', '--sw-primary-strong', '--sw-primary-soft',
                '--sw-primary-text', '--el-color-primary')

# 扫描的页面：与走查脚本一致的四条关键路径
PAGES = [
    ('feed', '/'),
    ('post-detail', '/post/1'),
    ('login', '/login'),
    ('publish', '/publish'),
]

MODES = ('light', 'dark')

# 运行时扫描：把每个可见文字元素的实际前景色与合成底色取出来
SCAN = r"""
() => {
  const parseColor = (s) => {
    if (!s) return null;
    s = String(s).trim();
    let m = s.match(/^rgba?\(([^)]+)\)$/i);
    if (m) {
      const p = m[1].split(/[,\s/]+/).filter(Boolean).map(parseFloat);
      if (p.length < 3) return null;
      return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
    }
    m = s.match(/^#([0-9a-f]{3,8})$/i);
    if (m) {
      let h = m[1];
      if (h.length === 3 || h.length === 4) h = h.split('').map(c => c + c).join('');
      return {
        r: parseInt(h.slice(0, 2), 16), g: parseInt(h.slice(2, 4), 16), b: parseInt(h.slice(4, 6), 16),
        a: h.length === 8 ? parseInt(h.slice(6, 8), 16) / 255 : 1,
      };
    }
    return null;
  };
  const over = (fg, bg) => ({
    r: fg.r * fg.a + bg.r * (1 - fg.a),
    g: fg.g * fg.a + bg.g * (1 - fg.a),
    b: fg.b * fg.a + bg.b * (1 - fg.a),
    a: 1,
  });
  const hex = (c) => '#' + [c.r, c.g, c.b].map(v => Math.round(v).toString(16).padStart(2, '0')).join('');
  const classOf = (el) => {
    const c = el.className;
    if (!c) return '';
    if (typeof c === 'string') return c;
    if (c.baseVal !== undefined) return c.baseVal;
    return String(c);
  };
  const chainOf = (el) => {
    const out = [];
    let n = el;
    for (let i = 0; i < 4 && n && n.tagName; i++) {
      const c = classOf(n);
      if (c) out.push(n.tagName.toLowerCase() + '.' + c.split(/\s+/).join('.'));
      n = n.parentElement;
    }
    return out.join(' < ');
  };
  const visible = (el) => {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    if (parseFloat(cs.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width >= 1 && r.height >= 1;
  };
  const hasOwnText = (el) => {
    for (const n of el.childNodes) if (n.nodeType === 3 && n.textContent.trim().length) return true;
    return false;
  };

  /* 线性渐变：按元素在渐变盒内的位置取实际颜色 */
  const parseGradient = (bgImage) => {
    if (!bgImage || bgImage.indexOf('linear-gradient') < 0) return null;
    const start = bgImage.indexOf('linear-gradient(');
    const end = bgImage.lastIndexOf(')');
    if (end < start) return null;
    const inner = bgImage.slice(start + 'linear-gradient('.length, end);
    const parts = [];
    let depth = 0, cur = '';
    for (const ch of inner) {
      if (ch === '(') depth++;
      else if (ch === ')') depth--;
      if (ch === ',' && depth === 0) { parts.push(cur.trim()); cur = ''; }
      else cur += ch;
    }
    if (cur.trim()) parts.push(cur.trim());
    const stops = [];
    for (const p of parts) {
      const cm = p.match(/^(rgba?\([^)]*\)|#[0-9a-fA-F]{3,8})/);
      if (!cm) continue;
      const color = parseColor(cm[1]);
      if (!color) continue;
      let pos = null;
      const pm = p.slice(cm[1].length).trim().match(/^(-?[\d.]+)%/);
      if (pm) pos = parseFloat(pm[1]) / 100;
      stops.push({ color, pos });
    }
    if (stops.length < 2) return null;
    for (let i = 0; i < stops.length; i++) {
      if (stops[i].pos === null) {
        if (i === 0) stops[i].pos = 0;
        else if (i === stops.length - 1) stops[i].pos = 1;
        else stops[i].pos = stops[i - 1].pos;
      }
    }
    stops.sort((a, b) => a.pos - b.pos);
    return { stops };
  };
  const gradAt = (g, host, el) => {
    const s = g.stops;
    const hr = host.getBoundingClientRect();
    const er = el.getBoundingClientRect();
    const t = hr.height ? Math.max(0, Math.min(1, (er.top + er.height / 2 - hr.top) / hr.height)) : 0.5;
    if (t <= s[0].pos) return s[0].color;
    for (let i = 1; i < s.length; i++) {
      if (t <= s[i].pos) {
        const a = s[i - 1], b = s[i];
        const span = b.pos - a.pos;
        const k = span <= 0 ? 0 : (t - a.pos) / span;
        return {
          r: a.color.r + (b.color.r - a.color.r) * k,
          g: a.color.g + (b.color.g - a.color.g) * k,
          b: a.color.b + (b.color.b - a.color.b) * k,
          a: a.color.a + (b.color.a - a.color.a) * k,
        };
      }
    }
    return s[s.length - 1].color;
  };
  const effectiveBg = (el) => {
    const layers = [];
    let node = el;
    let overImage = false;
    while (node && node.nodeType === 1) {
      const cs = getComputedStyle(node);
      if (cs.backgroundImage && cs.backgroundImage !== 'none') {
        const g = parseGradient(cs.backgroundImage);
        if (g) layers.push({ type: 'grad', grad: g, node });
        else { layers.push({ type: 'image' }); overImage = true; }
      }
      const c = parseColor(cs.backgroundColor);
      if (c && c.a > 0) layers.push({ type: 'color', color: c });
      node = node.parentElement;
    }
    let base = { r: 255, g: 255, b: 255, a: 1 };
    for (let i = layers.length - 1; i >= 0; i--) {
      const L = layers[i];
      if (L.type === 'color') base = over(L.color, base);
      else if (L.type === 'grad') base = over(gradAt(L.grad, L.node, el), base);
    }
    return { bg: base, overImage };
  };

  const texts = [];
  for (const el of document.querySelectorAll('*')) {
    if (!hasOwnText(el) || !visible(el)) continue;
    const txt = el.textContent.trim();
    if (!txt) continue;
    const cs = getComputedStyle(el);
    const fg = parseColor(cs.color);
    if (!fg) continue;
    const { bg, overImage } = effectiveBg(el);
    const effFg = fg.a < 1 ? over(fg, bg) : fg;
    texts.push({
      text: txt.slice(0, 40),
      cls: classOf(el).slice(0, 60),
      chain: chainOf(el),
      tag: el.tagName,
      color: hex(effFg),
      bg: hex(bg),
      overImage,
      fs: parseFloat(cs.fontSize),
      fw: parseInt(cs.fontWeight) || 400,
    });
  }

  /* 占位符：伪元素不参与上面这轮扫描，单独取 */
  const placeholders = [];
  for (const el of document.querySelectorAll('input, textarea')) {
    if (!visible(el)) continue;
    const cs = getComputedStyle(el, '::placeholder');
    const color = parseColor(cs.color);
    if (!color) continue;
    const { bg } = effectiveBg(el);
    placeholders.push({
      tag: el.tagName.toLowerCase(),
      placeholder: (el.getAttribute('placeholder') || '').slice(0, 30),
      color: hex(color),
      bg: hex(bg),
    });
  }
  return { texts, placeholders };
}
"""


# ---------- 令牌读取 ----------


def _blocks(text):
    """把 CSS 文本切成 (选择器, 声明块) 列表。"""
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    out = []
    for match in re.finditer(r'([^{}]+)\{', text):
        selector = ' '.join(match.group(1).split())
        depth = 1
        index = match.end()
        while index < len(text) and depth:
            if text[index] == '{':
                depth += 1
            elif text[index] == '}':
                depth -= 1
            index += 1
        out.append((selector, text[match.end():index - 1]))
    return out


def read_tokens(path):
    """读取亮色（:root）与暗色（.theme-dark 覆写）的令牌。"""
    text = path.read_text(encoding='utf-8')
    light = {}
    dark = {}
    for selector, body in _blocks(text):
        if selector == ':root':
            target = light
        elif selector == '.theme-dark':
            target = dark
        else:
            continue
        for m in re.finditer(r'(--[a-z0-9-]+)\s*:\s*([^;]+);', body):
            target.setdefault(m.group(1), m.group(2).strip())
    merged = dict(light)
    merged.update(dark)
    return {'light': light, 'dark': merged}


def resolve(tokens, name):
    """把令牌值解析成色值（跟随 var() 引用链）。"""
    seen = set()
    value = tokens.get(name)
    while value and value not in seen:
        seen.add(value)
        m = re.fullmatch(r'var\(\s*(--[a-z0-9-]+)\s*\)', value.strip())
        if not m:
            break
        value = tokens.get(m.group(1))
    return value.strip() if value else None


def as_hex(value):
    """把令牌色值转成 #rrggbb；不是实色则返回 None。"""
    if not value:
        return None
    value = value.strip().lower()
    if re.fullmatch(r'#[0-9a-f]{6}', value):
        return value
    if re.fullmatch(r'#[0-9a-f]{3}', value):
        return '#' + ''.join(c * 2 for c in value[1:])
    m = re.fullmatch(r'rgba?\(([^)]+)\)', value)
    if m:
        parts = [p.strip() for p in m.group(1).split(',')]
        if len(parts) >= 3:
            try:
                r, g, b = (int(float(p)) for p in parts[:3])
            except ValueError:
                return None
            return '#%02x%02x%02x' % (r, g, b)
    return None


def relative_luminance(hex_color):
    parts = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in parts]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(fg, bg):
    """WCAG 对比度。"""
    l1 = relative_luminance(fg)
    l2 = relative_luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


# ---------- 令牌级判定 ----------


def token_value_index(tokens):
    """色值 → 令牌名，用于把实测前景色反查成令牌。"""
    index = {}
    for name, value in tokens.items():
        color = as_hex(resolve(tokens, name))
        if color and color not in index:
            index[color] = name
    return index


def undefined_token_references(src_dir, tokens):
    """源码里引用了但 tokens.css 没定义的令牌。"""
    defined = set(tokens['light']) | set(tokens['dark'])
    findings = []
    for path in sorted(list(src_dir.rglob('*.vue')) + list(src_dir.rglob('*.ts')) + list(src_dir.rglob('*.css'))):
        if path.name == 'tokens.css':
            continue
        text = path.read_text(encoding='utf-8', errors='ignore')
        for m in re.finditer(r'var\(\s*(--[a-z0-9-]+)', text):
            if m.group(1) not in defined:
                findings.append({'file': str(path.relative_to(src_dir)), 'token': m.group(1)})
    return findings


def token_level_findings(tokens):
    """令牌级的对比度断言。

    覆盖正文、品牌文字、弱化文字与 Element Plus 的默认色覆写：
    每个令牌都要在自己会出现的底色上达到规范阈值（正文 ≥4.5:1、占位符 ≥4.0:1）。
    """
    findings = []

    def add(mode, issue, detail):
        findings.append({'mode': mode, 'issue': issue, 'detail': detail})

    for mode in MODES:
        toks = tokens[mode]
        body = as_hex(resolve(toks, '--sw-text'))
        for bg_name in ('--sw-bg', '--sw-surface'):
            bg = as_hex(resolve(toks, bg_name))
            if not body or not bg:
                continue
            ratio = contrast(body, bg)
            if ratio < BODY_MIN:
                add(mode, f'正文令牌 --sw-text 压 {bg_name} 仅 {ratio:.2f}:1',
                    f'{body} on {bg}')
        primary = as_hex(resolve(toks, '--sw-primary'))
        if primary:
            ratio = contrast('#ffffff', primary)
            if ratio < BODY_MIN:
                add(mode, f'白字压品牌主色 --sw-primary 仅 {ratio:.2f}:1',
                    f'#ffffff on {primary}')

        # 品牌文字令牌与弱化文字令牌：页底 / 卡片底 / 次级面 / 品牌浅底都要达正文阈值
        for token_name, bgs in (
            ('--sw-primary-text', ('--sw-bg', '--sw-surface', '--sw-surface-muted', '--sw-primary-soft')),
            ('--sw-text-muted', ('--sw-bg', '--sw-surface', '--sw-surface-muted')),
        ):
            fg = as_hex(resolve(toks, token_name))
            if not fg:
                continue
            for bg_name in bgs:
                bg = as_hex(resolve(toks, bg_name))
                if not bg:
                    continue
                ratio = contrast(fg, bg)
                if ratio < BODY_MIN:
                    add(mode, f'{token_name} 压 {bg_name} 仅 {ratio:.2f}:1', f'{fg} on {bg}')

        # Element Plus 默认色覆写：占位符 ≥4.0:1，次要/禁用文字 ≥4.5:1
        surface = as_hex(resolve(toks, '--sw-surface'))
        placeholder = as_hex(resolve(toks, '--el-text-color-placeholder'))
        if placeholder and surface:
            ratio = contrast(placeholder, surface)
            if ratio < PLACEHOLDER_MIN:
                add(mode, f'占位符 --el-text-color-placeholder 压卡片底仅 {ratio:.2f}:1',
                    f'{placeholder} on {surface}')
        for token_name in ('--el-text-color-secondary', '--el-disabled-text-color'):
            fg = as_hex(resolve(toks, token_name))
            if not fg or not surface:
                continue
            ratio = contrast(fg, surface)
            if ratio < BODY_MIN:
                add(mode, f'{token_name} 压卡片底仅 {ratio:.2f}:1', f'{fg} on {surface}')
        disabled_text = as_hex(resolve(toks, '--el-disabled-text-color'))
        disabled_bg = as_hex(resolve(toks, '--el-disabled-bg-color'))
        if disabled_text and disabled_bg:
            ratio = contrast(disabled_text, disabled_bg)
            if ratio < BODY_MIN:
                add(mode, f'--el-disabled-text-color 压禁用底仅 {ratio:.2f}:1',
                    f'{disabled_text} on {disabled_bg}')

    light = tokens['light']
    primary = as_hex(resolve(light, '--sw-primary'))
    surface = as_hex(resolve(light, '--sw-surface'))
    if primary and surface:
        ratio = contrast(primary, surface)
        if ratio < BODY_MIN:
            add('light', f'品牌主色 --sw-primary 压亮色卡片底仅 {ratio:.2f}:1',
                f'{primary} on {surface}')
    return findings


def verdict(ratio, need, over_image=False):
    """判定一次实测对比度的归属。

    品牌色文字 / 弱化文字 / 次要文字 / 其他令牌 / 字面量色值 / 占位符 一律阻断；
    只有照片底上的文字无法客观合成底色，记为观察项。
    """
    if ratio >= need:
        return 'pass'
    return 'observation' if over_image else 'blocking'


def classify(color, tokens, index):
    """把实测前景色反查成令牌，并给出角色。"""
    name = index.get(color.lower())
    if name is None:
        return name, '字面量色值'
    if name == '--sw-text':
        return name, '正文'
    if name in BRAND_TOKENS:
        return name, '品牌色文字'
    if name == '--sw-text-secondary':
        return name, '次要文字'
    if name == '--sw-text-muted':
        return name, '弱化文字'
    return name, '其他令牌'


def main():
    if not TOKENS_CSS.is_file():
        print(f'Error: 未找到令牌文件 {TOKENS_CSS}', file=sys.stderr)
        return 2
    if not (DIST_DIR / 'index.html').is_file():
        print(f'Error: 未找到构建产物 {DIST_DIR}，请先 npm run build:desktop', file=sys.stderr)
        return 2

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    tokens = read_tokens(TOKENS_CSS)
    index_by_mode = {mode: token_value_index(tokens[mode]) for mode in MODES}

    blocking = []
    observations = []

    for item in undefined_token_references(SRC_DIR, tokens):
        blocking.append({'kind': '未定义令牌', 'issue': f"{item['file']} 引用了未定义的令牌 {item['token']}"})
    for item in token_level_findings(tokens):
        blocking.append({'kind': '令牌级对比度', 'issue': f"{item['mode']}：{item['issue']}", 'detail': item['detail']})

    # playwright 与走查共用模块只在真正跑扫描时才需要：
    # 单元测试会导入本模块做令牌与对比度判定，那一步不装浏览器
    from playwright.sync_api import sync_playwright

    import desktop_mock_api
    from walkthrough_server import create_server, route_url, server_origin

    httpd, base_url = create_server(str(DIST_DIR))
    print(f'电脑端静态服务已启动：{base_url}/pc/')

    scanned = {}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=['--no-sandbox'])
            for mode in MODES:
                context = browser.new_context(viewport={'width': 1440, 'height': 900})
                # 主题持久化在 localStorage（桌面端沿用 sw_theme 键）
                context.add_init_script(
                    f"try {{ localStorage.setItem('sw_theme', '{mode}'); }} catch (e) {{}}")
                page = context.new_page()
                desktop_mock_api.install_routes(page, server_origin(base_url))
                for name, route in PAGES:
                    page.goto(route_url(base_url, route), wait_until='networkidle', timeout=45000)
                    page.wait_for_timeout(900)
                    result = page.evaluate(SCAN)
                    key = f'{name}:{mode}'
                    scanned[key] = result
                    index = index_by_mode[mode]
                    for item in result['texts']:
                        ratio = contrast(item['color'], item['bg'])
                        fs = item['fs']
                        fw = item['fw']
                        large = fs >= 24 or (fs >= 18.66 and fw >= 700)
                        need = LARGE_MIN if large else BODY_MIN
                        token, role = classify(item['color'], tokens[mode], index)
                        record = {
                            'page': key, 'role': role, 'token': token,
                            'text': item['text'], 'cls': item['cls'],
                            'color': item['color'], 'bg': item['bg'],
                            'ratio': round(ratio, 2), 'need': need,
                            'font_size': round(fs, 1),
                        }
                        if ratio < need:
                            record['over_image'] = item['overImage']
                            if verdict(ratio, need, item['overImage']) == 'blocking':
                                blocking.append({
                                    'kind': f'{role}对比度',
                                    'issue': (f"{key}：{role} {token or '字面量色值'}={item['color']}"
                                              f" 压底 {item['bg']} 仅 {ratio:.2f}:1（需 {need}:1）"),
                                    'detail': item['text'],
                                })
                            else:
                                observations.append(dict(record, kind='图片底文字未达标'))
                    for item in result['placeholders']:
                        ratio = contrast(item['color'], item['bg'])
                        if ratio < PLACEHOLDER_MIN:
                            if verdict(ratio, PLACEHOLDER_MIN) == 'blocking':
                                blocking.append({
                                    'kind': '占位符对比度',
                                    'issue': (f"{key}：占位符 {item['color']} 压底 {item['bg']}"
                                              f" 仅 {ratio:.2f}:1（需 {PLACEHOLDER_MIN}:1）"),
                                    'detail': item['placeholder'],
                                })
                            else:
                                observations.append({
                                    'page': key, 'role': '占位符', 'token': None,
                                    'text': item['placeholder'], 'cls': item['tag'],
                                    'color': item['color'], 'bg': item['bg'],
                                    'ratio': round(ratio, 2), 'need': PLACEHOLDER_MIN,
                                    'font_size': 0, 'kind': '占位符未达标',
                                })
                    print(f'   {key}: 文字 {len(result["texts"])} 个、占位符 {len(result["placeholders"])} 个')
                context.close()
            browser.close()
    finally:
        httpd.shutdown()

    report = {
        'tokens': {mode: {k: v for k, v in tokens[mode].items() if k.startswith('--sw-')} for mode in MODES},
        'thresholds': {'body': BODY_MIN, 'large': LARGE_MIN, 'placeholder': PLACEHOLDER_MIN},
        'blocking': blocking,
        'observations': observations,
        'scanned': {key: {'texts': len(value['texts']), 'placeholders': len(value['placeholders'])}
                    for key, value in scanned.items()},
        'status': 'FAIL' if blocking else 'PASS',
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f'\n阻断项 {len(blocking)} 条、观察项 {len(observations)} 条')
    for item in blocking:
        print('   [阻断]', item['issue'], item.get('detail', ''))
    grouped = {}
    for item in observations:
        grouped.setdefault(item['role'], []).append(item)
    for role, items in grouped.items():
        worst = min(items, key=lambda x: x['ratio'])
        print(f"   [观察] {role} {len(items)} 处，最低 {worst['ratio']}:1"
              f"（{worst['color']} on {worst['bg']}，{worst['page']}）")
    print(f'报告: {REPORT}')

    if blocking:
        print('[失败] 电脑端对比度门禁存在阻断项')
        return 1
    print('[通过] 电脑端亮/暗两套配色的对比度门禁通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
