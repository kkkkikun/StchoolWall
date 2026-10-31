#!/usr/bin/env python3
"""学生端外部请求守卫。

断言：打开页面时，H5 应用**不得**向第三方域名发请求。

为什么要有这条：
- uni-app H5 框架默认用 `body:after` 预加载导航阴影图，图片挂在 dcloud 公网 CDN
  （cdn.dcloud.net.cn）。实测每次打开页面都会多一次外网请求：CDN 不可达时浏览器
  控制台报 ERR_CONNECTION_CLOSED，被客观缺陷扫描当成真实缺陷，走查随机挂掉；
  同时用户 IP 与访问时间被泄漏给第三方。已在 App.vue 里关掉该伪元素，
  本脚本防止它（或别的第三方外呼）再回来。
- 本项目的对外依赖只有自家后端 `/api/v1/**`，那属于后端调用，不算外呼。

用法：python3 scripts/external-request-check.py --base-url http://127.0.0.1:8080
退出码非零 -> 存在第三方外呼。
"""

import argparse
import json
import os
import sys

from playwright.sync_api import sync_playwright

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPORT = os.path.join(ROOT_DIR, 'ci-artifacts', 'ui-walkthrough', 'external-requests.json')

# 覆盖主要页面：首页 / 发布 / 编辑资料 / 详情
ROUTES = [
    '/#/pages/index/index',
    '/#/pages/publish/index',
    '/#/pages/profile-edit/index',
    '/#/pages/post-detail/index?id=1',
]

# 自家后端接口不算外呼
API_PATH_MARK = '/api/v1/'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base-url', default='http://127.0.0.1:8080')
    args = ap.parse_args()

    base = args.base_url
    host = base.split('://', 1)[-1].split('/', 1)[0]

    external = []
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=['--no-sandbox'])
            ctx = browser.new_context(viewport={'width': 390, 'height': 844})
            page = ctx.new_page()

            def on_request(req):
                url = req.url
                if host in url or url.startswith('data:') or url.startswith('blob:'):
                    return
                if API_PATH_MARK in url:
                    return
                external.append(url)

            page.on('request', on_request)
            for route in ROUTES:
                page.goto(f'{base}{route}', wait_until='domcontentloaded')
                # 框架的阴影图预加载动画延迟 3 秒，等待足够长才能抓到
                page.wait_for_timeout(4500)
            browser.close()
    except Exception as exc:
        print(f'Error: 外部请求检查执行失败：{exc}', file=sys.stderr)
        return 2

    unique = sorted(set(external))
    report = {
        'base_url': base,
        'routes': ROUTES,
        'external_requests': unique,
        'external_request_count': len(external),
        'status': 'FAIL' if unique else 'PASS',
    }
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    if unique:
        print('[失败] H5 应用存在第三方外呼：')
        for u in unique:
            print('   -', u)
        print(f'报告: {REPORT}')
        return 1

    print(f'[通过] H5 应用无第三方外呼（检查 {len(ROUTES)} 个页面）')
    print(f'报告: {REPORT}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
