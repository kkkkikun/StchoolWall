#!/usr/bin/env python3
"""视觉 + 性能基线采集：逐页截图并记录首屏指标与资源健康度。

用法：python3 scripts/ui-perf-audit.py [页面关键字]
产物：/tmp/audit/*.png + /tmp/audit/metrics.json
"""

import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8080'
OUT = pathlib.Path('/tmp/audit')
OUT.mkdir(parents=True, exist_ok=True)

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

METRICS = """() => {
  const nav = performance.getEntriesByType('navigation')[0] || {};
  const paints = {};
  for (const p of performance.getEntriesByType('paint')) paints[p.name] = Math.round(p.startTime);
  const res = performance.getEntriesByType('resource');
  const byType = {};
  for (const r of res) {
    const t = r.initiatorType || 'other';
    byType[t] = byType[t] || { count: 0, bytes: 0, dur: 0 };
    byType[t].count++;
    byType[t].bytes += r.transferSize || 0;
    byType[t].dur += r.duration || 0;
  }
  const imgs = [...document.querySelectorAll('img')];
  const broken = imgs.filter(i => !i.complete || i.naturalWidth === 0);
  const slow = res.filter(r => r.duration > 300).map(r => r.name.split('/').pop() + ':' + Math.round(r.duration) + 'ms');
  return {
    fcp: paints['first-contentful-paint'] || 0,
    domContentLoaded: Math.round(nav.domContentLoadedEventEnd || 0),
    load: Math.round(nav.loadEventEnd || 0),
    domNodes: document.querySelectorAll('*').length,
    textLen: (document.body.innerText || '').length,
    images: imgs.length,
    brokenImages: broken.length,
    resources: res.length,
    byType,
    slowResources: slow.slice(0, 5),
    docScroll: document.documentElement.scrollWidth,
    docClient: document.documentElement.clientWidth,
  };
}"""


def main():
    report = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=['--no-sandbox'])
        ctx = browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2)
        page = ctx.new_page()
        for name, route, query in PAGES:
            for theme in ('light', 'dark'):
                page.goto(f'{BASE}/#/{route}{query}', wait_until='networkidle')
                page.evaluate(f"localStorage.setItem('sw_theme_mode','{theme}')")
                page.reload(wait_until='networkidle')
                page.wait_for_timeout(900)
                page.screenshot(path=str(OUT / f'{name}-{theme}.png'), full_page=False)
                if theme == 'light':
                    m = page.evaluate(METRICS)
                    m['page'] = name
                    report.append(m)
        browser.close()

    (OUT / 'metrics.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f"{'页面':<22}{'FCP':>7}{'DCL':>7}{'DOM':>7}{'图':>5}{'坏图':>6}{'资源':>7}  横向溢出")
    for m in report:
        overflow = '有' if m['docScroll'] > m['docClient'] + 1 else '-'
        print(f"{m['page']:<22}{m['fcp']:>6}ms{m['domContentLoaded']:>6}ms{m['domNodes']:>7}"
              f"{m['images']:>5}{m['brokenImages']:>6}{m['resources']:>7}  {overflow}")
    print(f"\n截图目录: {OUT}")


if __name__ == '__main__':
    main()
