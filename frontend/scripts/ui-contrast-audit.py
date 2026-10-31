#!/usr/bin/env python3
"""客观缺陷批量扫描：对比度 / 横向裁切 / 文字裁切 / 点击区 / 字号 / 坏图 / 横向溢出。

对亮/暗双模式逐页执行，输出结构化 JSON 报告。
用法：python3 scripts/ui-contrast-audit.py [页面关键字]
产物：/tmp/audit/contrast_audit.json

判定口径（与 openspec/specs/frontend-ui/spec.md 一致）：
- 对比度：沿祖先链合成实色层与线性渐变（渐变按元素位置取实际 alpha），
  底色未知处按最坏情况（纯白）取，得到的是**下界**；仍不达标才算缺陷。
- 品牌色例外：品牌色小字链接、以及白字压品牌色底的品牌主按钮，
  按令牌实际色值识别（从 App.vue 读 --primary 系列），单列计数不阻断。
- 点击区：元素自身或其最近的**同类可点击祖先**需 ≥ 32×32，装饰性图标不计。
- 横向裁切：自带渐隐层的横向滚动容器属于设计内，不算裁切缺陷。
"""
import json
import pathlib
import re
import sys

from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8080'
OUT = pathlib.Path('/tmp/audit')
SRC_ROOT = pathlib.Path(__file__).resolve().parent.parent / 'src'

PAGES = [
    ('index', 'pages/index/index', ''),
    ('group', 'pages/group/index', ''),
    ('publish', 'pages/publish/index', ''),
    ('profile-edit', 'pages/profile-edit/index', ''),
    ('hot', 'pages/hot/index', ''),
    ('interactions', 'pages/interactions/index', ''),
    ('message', 'pages/message/index', ''),
    ('announcement-detail', 'pages/announcement-detail/index', '?id=1'),
    ('activity', 'pages/activity/index', '?id=1'),
    ('tag-posts', 'pages/tag-posts/index', '?id=1'),
    ('hot-users', 'pages/hot-users/index', ''),
    ('mine', 'pages/mine/index', ''),
    ('auth', 'pages/auth/index', ''),
    ('post-detail', 'pages/post-detail/index', '?id=1'),
    ('search', 'pages/search/index', ''),
    ('party-create', 'pages/party-create/index', ''),
    ('profile', 'pages/profile/index', '?id=u1001'),
    ('settings', 'pages/settings/index', ''),
    ('oauth-callback', 'pages/oauth-callback/index', '?code=mock&state=mock'),
    ('verify', 'pages/verify/index', ''),
    ('tags', 'pages/tags/index', ''),
    ('admin', 'pages/admin/index', ''),
    ('my-posts', 'pages/my-posts/index', ''),
    ('appeals', 'pages/appeals/index', ''),
    ('blocks', 'pages/blocks/index', ''),
]

# 品牌主色：既作品牌小字，也作主按钮底色；具体色值由 App.vue 令牌决定
MIN_TAP = 32          # 最小点击区（px）
MIN_FONT = 11         # 最小字号（px），对应 22rpx @390 宽

# ---- 源码级静态守卫：覆盖「当前 mock 数据未渲染」的状态 ----
# 按令牌**实际色值**判定，而不是写死某个品牌的色名：换品牌同样有效。
_TEXT_COLOR_VAR = re.compile(r'(?:^|[;{\s])color\s*:\s*var\((--[a-z0-9-]+)\)')
_BG_VAR = re.compile(r'(?:^|[;{\s])background(?:-color)?\s*:\s*[^;]*?var\((--[a-z0-9-]+)\)')
_WHITE_FG = re.compile(r'(?:^|[;{\s])color\s*:\s*(?:var\(--text-inverse\)|#fff\b|white\b)')
# 既定例外：底栏激活态（图标与文字同色，属品牌签名元素，单独计数）
_TEXT_EXCEPTIONS = ('.tab-label.active', '.tab-item.active')


def _hex_lum(value: str):
    """#rrggbb 的相对亮度；非 hex（rgba/渐变/变量链）返回 None。"""
    m = re.fullmatch(r'#([0-9a-fA-F]{6})', value.strip())
    if not m:
        return None
    ch = m.group(1)
    parts = [int(ch[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in parts]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a: str, b: str):
    la, lb = _hex_lum(a), _hex_lum(b)
    if la is None or lb is None:
        return None
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def read_tokens(app_vue: pathlib.Path):
    """从 App.vue 读取亮色/暗色令牌的实际色值。"""
    text = app_vue.read_text(encoding='utf-8')
    light_block = text.split('.theme-dark {')[0]
    dark_block = ('.theme-dark {' + text.split('.theme-dark {')[1]) if '.theme-dark {' in text else ''
    out = {}
    for mode, block in (('light', light_block), ('dark', dark_block)):
        toks = {}
        # 捕获全部令牌定义（颜色、圆角、渐变…），对比度判定时再筛 hex
        for m in re.finditer(r'(--[a-z0-9-]+)\s*:\s*([^;]+);', block):
            toks.setdefault(m.group(1), m.group(2).strip())
        out[mode] = toks
    return out


def brand_colors(src_root: pathlib.Path):
    """品牌色集合（从 App.vue 的 --primary 系列令牌读取），用于「既定例外」分类。"""
    toks = read_tokens(src_root / 'App.vue')['light']
    names = ('--primary', '--primary-strong', '--primary-fill', '--primary-text')
    return sorted({toks[n].lower() for n in names if n in toks})


def css_lint(src_root: pathlib.Path):
    """扫描 .vue 源码，找出即便当前 mock 数据未渲染也会露出的对比度问题。

    判定按令牌**实际色值**做，换品牌同样有效：
    - 文字色与「本规则自己的背景」比；本规则无背景时才退回页面底
    - 填充面（背景）与同规则白字比
    - 引用了 App.vue 未定义的令牌 → 直接报错
    """
    tokens = read_tokens(src_root / 'App.vue')
    light, dark = tokens['light'], tokens['dark']
    findings = []

    # 1) 令牌完整性：源码引用的每个变量都必须在 App.vue 有定义
    defined = set(light) | set(dark)
    for path in sorted(list(src_root.rglob('*.vue')) + list(src_root.rglob('*.ts'))):
        if path.name == 'App.vue':
            continue
        for m in re.finditer(r'var\((--[a-z0-9-]+)', path.read_text(encoding='utf-8', errors='ignore')):
            if m.group(1) not in defined:
                findings.append({
                    'file': str(path.relative_to(src_root)), 'rule': '令牌引用',
                    'issue': f'引用了未定义的令牌 {m.group(1)}', 'decl': m.group(0),
                })

    # 2) 规则内对比度
    for path in sorted(src_root.rglob('*.vue')):
        text = path.read_text(encoding='utf-8')
        rel = str(path.relative_to(src_root))
        for style in re.findall(r'<style[^>]*>(.*?)</style>', text, re.S):
            for rule in re.finditer(r'([^{}]+)\{([^{}]*)\}', style):
                selector = ' '.join(rule.group(1).split())
                body = rule.group(2)
                if any(exc in selector for exc in _TEXT_EXCEPTIONS):
                    continue
                for mode, toks in (('light', light), ('dark', dark)):
                    page_bg = toks.get('--bg-page')
                    if not page_bg:
                        continue
                    # 本规则自身的背景
                    own_bg = None
                    for m in _BG_VAR.finditer(body):
                        val = toks.get(m.group(1))
                        if val and re.fullmatch(r'#[0-9a-fA-F]{6}', val):
                            own_bg = val
                            break
                    if own_bg is None:
                        m = re.search(r'background(?:-color)?\s*:\s*(#[0-9a-fA-F]{6})', body)
                        if m:
                            own_bg = m.group(1)
                    bg = own_bg or page_bg
                    # 文字色：token 或字面量
                    # --text-inverse（白字）只在填充面上成立，底色由运行时审计按实际
                    # 渐变/图片合成判定，静态层无法确定，故跳过
                    for m in _TEXT_COLOR_VAR.finditer(body):
                        if m.group(1) == '--text-inverse':
                            continue
                        val = toks.get(m.group(1))
                        if not val or not re.fullmatch(r'#[0-9a-fA-F]{6}', val):
                            continue
                        r = _contrast(val, bg)
                        if r is not None and r < 4.5:
                            findings.append({
                                'file': rel, 'rule': selector[:90],
                                'issue': f'{mode} 文字 {m.group(1)}={val} 压底 {bg} 仅 {r:.2f}:1',
                                'decl': f'color: var({m.group(1)})',
                            })
                    # 填充面 + 白字
                    if own_bg and _WHITE_FG.search(body):
                        r = _contrast('#ffffff', own_bg)
                        if r is not None and r < 4.5:
                            findings.append({
                                'file': rel, 'rule': selector[:90],
                                'issue': f'{mode} 填充面 {own_bg} 配白字仅 {r:.2f}:1',
                                'decl': 'background + color: var(--text-inverse)',
                            })
    seen = set()
    uniq = []
    for f in findings:
        key = (f['file'], f['rule'], f['issue'], f['decl'])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(f)
    return uniq


SCAN = r"""
(opts) => {
  const { BRAND, MIN_TAP, MIN_FONT } = opts;

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
  const lum = (c) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  };
  const ratio = (a, b) => { const l1 = lum(a), l2 = lum(b); const hi = Math.max(l1, l2), lo = Math.min(l1, l2); return (hi + 0.05) / (lo + 0.05); };
  const hex = (c) => '#' + [c.r, c.g, c.b].map(v => Math.round(v).toString(16).padStart(2, '0')).join('');

  /* ---------- 线性渐变解析与取色 ---------- */
  const parseLinearGradient = (bgImage) => {
    if (!bgImage || bgImage.indexOf('linear-gradient') < 0) return null;
    const start = bgImage.indexOf('linear-gradient(');
    const end = bgImage.lastIndexOf(')');
    if (end < start) return null;
    const inner = bgImage.slice(start + 'linear-gradient('.length, end);
    const parts = []; let depth = 0, cur = '';
    for (const ch of inner) {
      if (ch === '(') depth++;
      else if (ch === ')') depth--;
      if (ch === ',' && depth === 0) { parts.push(cur.trim()); cur = ''; }
      else cur += ch;
    }
    if (cur.trim()) parts.push(cur.trim());
    if (parts.length < 2) return null;
    let angle = 180, rest = parts;
    if (/deg$|turn$|rad$|grad$/i.test(parts[0])) {
      const a = parts[0].trim();
      angle = a.endsWith('deg') ? parseFloat(a)
             : a.endsWith('turn') ? parseFloat(a) * 360
             : 180;
      rest = parts.slice(1);
    }
    const stops = [];
    for (const p of rest) {
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
    // 补齐缺省位置
    for (let i = 0; i < stops.length; i++) {
      if (stops[i].pos === null) {
        if (i === 0) stops[i].pos = 0;
        else if (i === stops.length - 1) stops[i].pos = 1;
        else stops[i].pos = stops[i - 1].pos;
      }
    }
    stops.sort((a, b) => a.pos - b.pos);
    return { angle, stops };
  };
  const gradAt = (g, t) => {
    const s = g.stops;
    t = Math.max(0, Math.min(1, t));
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
  // 元素在渐变盒内的位置（0=起点 1=终点）
  const gradientT = (grad, host, el) => {
    const hr = host.getBoundingClientRect();
    const er = el.getBoundingClientRect();
    const a = ((grad.angle % 360) + 360) % 360;
    if (Math.abs(a - 180) < 2) {                    // to bottom
      if (!hr.height) return 0.5;
      return (er.top + er.height / 2 - hr.top) / hr.height;
    }
    if (Math.abs(a - 0) < 2 || Math.abs(a - 360) < 2) {  // to top
      if (!hr.height) return 0.5;
      return 1 - (er.top + er.height / 2 - hr.top) / hr.height;
    }
    if (Math.abs(a - 90) < 2) {                     // to right
      if (!hr.width) return 0.5;
      return (er.left + er.width / 2 - hr.left) / hr.width;
    }
    if (Math.abs(a - 270) < 2) {                    // to left
      if (!hr.width) return 0.5;
      return 1 - (er.left + er.width / 2 - hr.left) / hr.width;
    }
    return 0.5;
  };

  /* ---------- 有效背景合成 ---------- */
  const effectiveBg = (el) => {
    const layers = [];   // 由内向外
    let node = el;
    let overImage = false;
    while (node && node.nodeType === 1) {
      const cs = getComputedStyle(node);
      if (cs.backgroundImage && cs.backgroundImage !== 'none') {
        const g = parseLinearGradient(cs.backgroundImage);
        if (g) layers.push({ type: 'grad', grad: g, node });
        else { layers.push({ type: 'image' }); overImage = true; }
      }
      const c = parseColor(cs.backgroundColor);
      if (c && c.a > 0) layers.push({ type: 'color', color: c });
      node = node.parentElement;
    }
    // 由外向内合成；图片层用最坏情况（纯白）代替
    let base = { r: 255, g: 255, b: 255, a: 1 };
    for (let i = layers.length - 1; i >= 0; i--) {
      const L = layers[i];
      if (L.type === 'color') base = over(L.color, base);
      else if (L.type === 'grad') base = over(gradAt(L.grad, gradientT(L.grad, L.node, el)), base);
      // image 层：保持 base（最坏情况纯白）
    }
    return { bg: base, overImage };
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
    for (let i = 0; i < 5 && n && n.tagName; i++) {
      const c = classOf(n);
      if (c) out.push(n.tagName.toLowerCase() + '.' + c.split(/\s+/).join('.'));
      n = n.parentElement;
    }
    return out.join(' < ');
  };

  const results = {
    contrast: [], contrastBrand: [], contrastUnknown: [],
    clipped: [], clippedText: [], smallTap: [], tinyText: [], broken: [], overflowX: [],
  };

  /* ---------- 对比度 ---------- */
  for (const el of document.querySelectorAll('*')) {
    if (!hasOwnText(el)) continue;
    if (!visible(el)) continue;
    const txt = el.textContent.trim();
    if (!txt) continue;
    const cs = getComputedStyle(el);
    const fg = parseColor(cs.color);
    if (!fg) continue;
    const { bg, overImage } = effectiveBg(el);
    const effFg = fg.a < 1 ? over(fg, bg) : fg;
    const cr = ratio(effFg, bg);
    const fs = parseFloat(cs.fontSize);
    const fw = parseInt(cs.fontWeight) || 400;
    const large = fs >= 24 || (fs >= 18.66 && fw >= 700);
    const need = large ? 3.0 : 4.5;
    const rec = {
      text: txt.slice(0, 40),
      cls: classOf(el).slice(0, 60),
      chain: chainOf(el),
      tag: el.tagName,
      color: hex(effFg), bg: hex(bg),
      fs: Math.round(fs * 10) / 10, ratio: Math.round(cr * 100) / 100, need,
    };
    if (cr >= need) continue;
    const fgHex = hex(effFg).toLowerCase(), bgHex = hex(bg).toLowerCase();
    // 既定例外：品牌蓝蓝字链接 / 白字压品牌蓝底的品牌主按钮
    if (BRAND.includes(fgHex) || (effFg.r === 255 && effFg.g === 255 && effFg.b === 255 && BRAND.includes(bgHex))) {
      results.contrastBrand.push(rec);
    } else if (overImage) {
      // 底色为照片：已按最坏情况（纯白）合成，仍不达标才是真缺陷
      results.contrast.push(rec);
    } else {
      results.contrast.push(rec);
    }
  }

  /* ---------- 横向裁切（无渐隐层的滚动容器才算缺陷）---------- */
  for (const sv of document.querySelectorAll('uni-scroll-view, .uni-scroll-view, .uni-scroll-view-content, .uni-scroll-view-hd')) {
    const cs = getComputedStyle(sv);
    if (cs.overflowX !== 'auto' && cs.overflowX !== 'scroll') continue;
    if (sv.scrollWidth <= sv.clientWidth + 2) continue;
    // 设计内：同层存在渐隐覆盖层（滚动提示）
    let hasFade = false;
    let scope = sv.parentElement;
    for (let d = 0; d < 3 && scope && !hasFade; d++) {
      if (scope.querySelector && scope.querySelector('[class*="fade"]')) hasFade = true;
      scope = scope.parentElement;
    }
    if (hasFade) continue;
    const r = sv.getBoundingClientRect();
    results.clipped.push({
      cls: classOf(sv).slice(0, 50),
      scrollW: sv.scrollWidth, clientW: sv.clientWidth,
      overflowPx: sv.scrollWidth - sv.clientWidth,
    });
  }

  /* ---------- 点击区：真实带事件监听的元素需 ≥ MIN_TAP ----------
     Vue 3 把事件挂载在元素的 Symbol(_vei) 上，可精确区分
     「可点击控件」与「同名的信息性文本」，避免按类名猜测。 */
  const hasHandler = (el) => {
    for (const s of Object.getOwnPropertySymbols(el)) {
      if (s.toString() !== 'Symbol(_vei)') continue;
      const v = el[s];
      if (v && typeof v === 'object') return Object.keys(v).length > 0;
    }
    return false;
  };
  for (const el of document.querySelectorAll('*')) {
    if (!hasHandler(el)) continue;
    if (!visible(el)) continue;
    // 框架内置控件的内部元素不单独判定：
    // - uni-input 内部的 form/input：真实控件是外层 uni-input
    // - uni-swiper-dot：分页指示点，视觉按 X 风格保持小圆点
    if (el.closest('uni-input')) continue;
    if (el.classList && el.classList.contains('uni-swiper-dot')) continue;
    const r = el.getBoundingClientRect();
    if (r.width >= MIN_TAP && r.height >= MIN_TAP) continue;
    results.smallTap.push({
      cls: classOf(el).slice(0, 60), tag: el.tagName,
      w: Math.round(r.width), h: Math.round(r.height),
      chain: chainOf(el),
    });
  }

  /* ---------- 字号过小 ---------- */
  for (const el of document.querySelectorAll('*')) {
    if (!hasOwnText(el)) continue;
    if (!visible(el)) continue;
    const fs = parseFloat(getComputedStyle(el).fontSize);
    if (fs < MIN_FONT) {
      results.tinyText.push({
        text: el.textContent.trim().slice(0, 30),
        cls: classOf(el).slice(0, 60), fs: Math.round(fs * 10) / 10,
        chain: chainOf(el),
      });
    }
  }

  /* ---------- 文本被固定高度容器裁切 ---------- */
  for (const el of document.querySelectorAll('*')) {
    if (!visible(el)) continue;
    const txt = (el.textContent || '').trim();
    if (!txt) continue;
    if (el.clientHeight <= 0 || el.clientHeight > 80) continue;
    if (el.scrollHeight <= el.clientHeight + 2) continue;
    const cs = getComputedStyle(el);
    if (cs.textOverflow === 'ellipsis') continue;
    if (cs.display === 'inline') continue;
    results.clippedText.push({
      text: txt.slice(0, 30),
      cls: classOf(el).slice(0, 60),
      chain: chainOf(el),
      clientH: el.clientHeight, scrollH: el.scrollHeight,
      fontSize: Math.round(parseFloat(cs.fontSize) * 10) / 10,
      overflow: cs.overflow,
    });
  }

  /* ---------- 坏图 / 横向溢出 ---------- */
  for (const img of document.querySelectorAll('img')) {
    if (!img.complete || img.naturalWidth === 0) {
      results.broken.push({ src: (img.getAttribute('src') || '').slice(0, 120) });
    }
  }
  const de = document.documentElement;
  if (de.scrollWidth > de.clientWidth + 1) {
    results.overflowX.push({ scrollW: de.scrollWidth, clientW: de.clientWidth });
  }
  return results;
}
"""


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox'])
        for mode in ('light', 'dark'):
            # 主题在模块加载时从 storage 读取，必须在页面脚本执行前注入
            ctx = browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2)
            ctx.add_init_script(
                f"try {{ localStorage.setItem('sw_theme_mode', '{mode}'); }} catch (e) {{}}")
            page = ctx.new_page()
            for name, path, query in PAGES:
                if only and only not in name:
                    continue
                page.goto(f'{BASE}/#{path}{query}', wait_until='networkidle')
                page.wait_for_timeout(900)
                r = page.evaluate(SCAN, {
                    'BRAND': brand_colors(SRC_ROOT), 'MIN_TAP': MIN_TAP, 'MIN_FONT': MIN_FONT,
                })
                report[f'{name}:{mode}'] = r
                print(f'{name}:{mode} contrast={len(r["contrast"])} brand={len(r["contrastBrand"])} '
                      f'clipped={len(r["clipped"])} clipText={len(r["clippedText"])} '
                      f'smallTap={len(r["smallTap"])} tinyText={len(r["tinyText"])} '
                      f'broken={len(r["broken"])} overflowX={len(r["overflowX"])}')
            ctx.close()
        browser.close()
    total = sum(len(r['contrast']) for r in report.values())
    brand = sum(len(r['contrastBrand']) for r in report.values())
    tap = sum(len(r['smallTap']) for r in report.values())
    tiny = sum(len(r['tinyText']) for r in report.values())
    clip = sum(len(r['clipped']) for r in report.values())
    lint = css_lint(SRC_ROOT)
    report['__cssLint__'] = lint
    (OUT / 'contrast_audit.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'\n真实缺陷合计: 对比度={total} 点击区={tap} 小字号={tiny} 横向裁切={clip} '
          f'源码静态={len(lint)} | 品牌既定例外={brand}')
    for f in lint:
        print(f"  [静态] {f['file']} :: {f['rule']} :: {f['issue']} ({f['decl']})")
    print('wrote', OUT / 'contrast_audit.json')


if __name__ == '__main__':
    main()
