#!/usr/bin/env python3
"""电脑端走查与对比度审计共用的接口 mock 夹具。

页面必须在「有内容」的状态下渲染，否则断言会退化成空页面检查。这里不连接真实后端，
夹具里也没有任何真实用户数据：昵称一律是假名、头像留空，不出现真实姓名与学号。

后端所有端点都包在 `{code, data}` 信封里（见 desktop-frontend/src/utils/http.ts），
mock 也按同一信封返回，前端的解包逻辑才能真正跑到。
"""

import json

# 登录成功后的会话：访问令牌只是内存里的假值
SESSION = {
    'access_token': 'mock-access-token',
    'refresh_token': 'mock-refresh-token',
    'csrf_token': 'mock-csrf-token',
    'role': 'student',
    'user_info': {'id': '1001', 'nickname': '走查测试员', 'is_verified': True},
}

# 未登录时刷新通道的返回值：没有 user_info，前端据此判定「未登录」
ANONYMOUS_REFRESH = {}

# 会话状态：访问令牌只存在前端内存里，刷新页面后要走刷新通道换回来。
# mock 记住「是否已经登录过」，刷新通道据此返回会话或空信封 —— 与真实行为一致。
SESSION_STATE = {'logged_in': False}

TAGS = [
    {'id': 1, 'name': '失物招领'},
    {'id': 2, 'name': '二手交易'},
    {'id': 3, 'name': '拼车'},
]

HOT_USERS = [
    {'id': '1001', 'nickname': '林同学', 'heat': 320},
    {'id': '1002', 'nickname': '陈同学', 'heat': 210},
]


def _post(post_id, content, nickname='林同学', user_id='1001', comments=2, images=None):
    return {
        'id': post_id,
        'post_type': 'general',
        'content': content,
        'images': images or [],
        'status': 1,
        'is_pinned': False,
        'is_featured': False,
        'created_at': '2026-11-03T08:00:00',
        'updated_at': '2026-11-03T08:00:00',
        'user': {'id': int(user_id), 'nickname': nickname, 'avatar_url': None},
        'user_id': user_id,
        'tags': [{'id': 1, 'name': '失物招领'}],
        'category': None,
        'like_count': 12,
        'comment_count': comments,
        'view_count': 88,
        'is_liked': False,
        'is_favorited': False,
    }


POSTS = [
    _post(1, '在图书馆三楼捡到一张校园卡，失主请私聊我。', '林同学'),
    _post(2, '出一辆九成新的自行车，附送车锁，售价面议。', '陈同学', user_id='1002'),
    _post(3, '周五晚拼车回学校，还剩两个位置。', '周同学', user_id='1003'),
]

COMMENTS = [
    {
        'id': 5001,
        'post_id': 1,
        'user_id': '1002',
        'user': {'nickname': '陈同学', 'avatar_url': None},
        'content': '谢谢好心人！',
        'created_at': '2026-11-03T09:00:00',
    },
]

BANNERS = {
    'items': [
        {
            'id': 1,
            'title': '开学季 · 校园墙全新上线',
            'desc': '发帖前记得看一下版块说明',
            'tag': '公告',
            'image_url': None,
            'link_url': None,
            'post_id': None,
            'activity_id': None,
        }
    ]
}


def _page(items):
    return {'items': items, 'next_cursor': None, 'has_more': False}


def dispatch(method, path):
    """按方法与路径返回信封里的 data 部分。"""
    if method == 'POST':
        if path == '/auth/web-login':
            SESSION_STATE['logged_in'] = True
            return SESSION
        if path == '/auth/register':
            SESSION_STATE['logged_in'] = True
            return SESSION
        if path == '/auth/refresh':
            return SESSION if SESSION_STATE['logged_in'] else ANONYMOUS_REFRESH
        if path == '/auth/logout':
            SESSION_STATE['logged_in'] = False
            return {}
        if path == '/posts':
            return {'post_id': 101, 'status': 1}
        if path.endswith('/like'):
            return {'liked': True, 'like_count': 13}
        if path.endswith('/favorite'):
            return {'favorited': True}
        if path.endswith('/comments'):
            return COMMENTS[0]
        return {}

    # GET
    if path == '/posts':
        return _page(POSTS)
    if path == '/posts/hot':
        return {'items': POSTS}
    if path == '/posts/featured':
        return _page(POSTS)
    if path == '/posts/search':
        return _page(POSTS)
    if path == '/posts/my':
        return {'items': POSTS[:1]}
    if path.startswith('/posts/') and path.endswith('/comments'):
        return _page(COMMENTS)
    if path.startswith('/posts/'):
        return POSTS[0]
    if path == '/tags':
        return TAGS
    if path == '/banners':
        return BANNERS
    if path == '/user/hot-ranking':
        return {'items': HOT_USERS}
    if path == '/notifications':
        return _page([])
    if path == '/notifications/unread-summary':
        return {'like': 0, 'comment': 0, 'follow': 0, 'system': 0}
    if path == '/runtime-controls':
        return {'publish_enabled': True}
    return {}


def _strip_api_base(path):
    """去掉 API 基址前缀；CI 里 VITE_API_BASE_URL 可能指向绝对地址，路径片段仍相同。"""
    marker = '/api/v1'
    if marker in path:
        return path.split(marker, 1)[1] or '/'
    return path


def _cors_headers(request):
    """跨域时的 CORS 头。

    带凭据的请求（axios `withCredentials`）不能靠 `Access-Control-Allow-Headers: *` ——
    通配符只在不带凭据时生效，所以这里把预检里请求的头原样回回去。
    """
    origin = request.headers.get('origin') or '*'
    requested = request.headers.get('access-control-request-headers') or '*'
    return {
        'Access-Control-Allow-Origin': origin,
        'Access-Control-Allow-Credentials': 'true',
        'Access-Control-Allow-Headers': requested,
        'Access-Control-Allow-Methods': '*',
    }


def mock_api(route):
    """Playwright 路由处理器：拦截 /api/v1/** 并按信封返回夹具。"""
    request = route.request
    headers = _cors_headers(request)
    if request.method == 'OPTIONS':
        route.fulfill(status=204, headers=headers, body='')
        return

    path = _strip_api_base(request.url.split('?')[0])
    try:
        data = dispatch(request.method, path)
    except Exception:  # 夹具没覆盖到的路径按空信封返回，避免 404 变成控制台错误
        data = {}
    route.fulfill(
        status=200,
        content_type='application/json',
        headers=headers,
        body=json.dumps({'code': 0, 'data': data}, ensure_ascii=False),
    )


def is_api_url(url, origin=None):
    """判断请求是不是后端接口调用。

    - 路径里带 `/api/v1` 的（同源相对基址，默认情形）；
    - 跨域的：电脑端不加载任何外部静态资源，跨域请求一律是接口调用 ——
      CI 里 `VITE_API_BASE_URL` 可能指向绝对地址，不能让走查真的打到线上接口。
    """
    text = str(url).split('?', 1)[0]
    host = ''
    path = text
    if '://' in text:
        rest = text.split('://', 1)[1]
        host, _, tail = rest.partition('/')
        path = '/' + tail
    if '/api/v1' in path:
        return True
    if origin and host and host != origin:
        return True
    return False


def install_routes(page, origin=None):
    """把 mock 装到页面上。origin 为静态服务所在主机名（不含协议）。"""
    page.route(lambda url: is_api_url(url, origin), mock_api)
