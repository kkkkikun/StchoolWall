#!/usr/bin/env python3
"""
SchoolWall 学生端 H5 走查共享 Mock API（单一数据源）。
Fixture 完全对齐 backend/app/services/post.py 的 _post_to_dict 契约。
供 ui-walkthrough.py（移动端 390x844）与 ui-walkthrough-desktop.py（桌面/平板）共同使用，
避免多套 Mock 数据漂移。
"""

import json
import urllib.parse

# 标准后端响应 Fixture（完全对齐 backend/app/services/post.py 的 _post_to_dict）
HOT_POSTS_FIXTURE = [
    {
        'id': 1,
        'post_type': 'general',
        'category': '学习考研',
        'content': '图书馆自习室预约新规则讨论\n大家觉得现在的预约时间合理吗？建议增加临时取消违约机制。',
        'images': [],
        'price': None,
        'status': 1,
        'is_pinned': False,
        'is_featured': False,
        'user': {'nickname': '自习达人', 'avatar_url': None},
        'like_count': 15,
        'comment_count': 8,
        'view_count': 21000,
        'is_liked': False,
        'is_favorited': False,
        'created_at': '2026-10-21T08:00:00Z',
    },
    {
        'id': 2,
        'post_type': 'general',
        'category': '校园生活',
        'content': '二食堂新品评测征集！\n窗口新出的石锅拌饭和烧鸭面大家尝过了吗？',
        'images': [],
        'price': None,
        'status': 1,
        'is_pinned': False,
        'is_featured': False,
        'user': {'nickname': '美食小侦探', 'avatar_url': None},
        'like_count': 9,
        'comment_count': 12,
        'view_count': 15000,
        'is_liked': False,
        'is_favorited': False,
        'created_at': '2026-10-21T07:30:00Z',
    },
    {
        'id': 3,
        'post_type': 'second_hand',
        'category': '二手',
        'content': '毕业甩卖：99新考研英语/政治真题全套\n仅自提，附送复试专业课笔记。',
        'images': [],
        'price': 45.0,
        'status': 1,
        'is_pinned': False,
        'is_featured': False,
        'user': {'nickname': '考研上岸学长', 'avatar_url': None},
        'like_count': 4,
        'comment_count': 2,
        'view_count': 8600,
        'is_liked': False,
        'is_favorited': False,
        'created_at': '2026-10-21T06:00:00Z',
    },
    {
        'id': 4,
        'post_type': 'general',
        'category': '校园生活',
        'content': '南湖音乐节志愿者招募开启\n需要现场检票和指引，有志愿学时！',
        'images': [],
        'price': None,
        'status': 1,
        'is_pinned': False,
        'is_featured': False,
        'user': {'nickname': '学生会文艺部', 'avatar_url': None},
        'like_count': 2,
        'comment_count': 1,
        'view_count': 3200,
        'is_liked': False,
        'is_favorited': False,
        'created_at': '2026-10-21T05:00:00Z',
    },
    {
        'id': 5,
        'post_type': 'general',
        'category': '学习考研',
        'content': '计算机系 ACM 校队招新宣讲会安排\n本周五晚七点在实验楼报告厅，欢迎零基础同学报名。',
        'images': [],
        'price': None,
        'status': 1,
        'is_pinned': False,
        'is_featured': False,
        'user': {'nickname': 'ACM集训队', 'avatar_url': None},
        'like_count': 7,
        'comment_count': 4,
        'view_count': 2800,
        'is_liked': False,
        'is_favorited': False,
        'created_at': '2026-10-21T04:30:00Z',
    },
    {
        'id': 6,
        'post_type': 'general',
        'category': '运动健身',
        'content': '羽毛球馆周末约球组队，四缺二！\n周六下午三点到五点，场地已订好，双打水平中等即可。',
        'images': [],
        'price': None,
        'status': 1,
        'is_pinned': False,
        'is_featured': False,
        'user': {'nickname': '羽毛球爱好者', 'avatar_url': None},
        'like_count': 5,
        'comment_count': 6,
        'view_count': 1900,
        'is_liked': False,
        'is_favorited': False,
        'created_at': '2026-10-21T04:00:00Z',
    },
    {
        'id': 7,
        'post_type': 'general',
        'category': '学习考研',
        'content': '考研数学复习经验贴：高数重难点梳理\n整理了近五年真题常考的微分中值定理与无穷级数题型。',
        'images': [],
        'price': None,
        'status': 1,
        'is_pinned': False,
        'is_featured': False,
        'user': {'nickname': '数学课代表', 'avatar_url': None},
        'like_count': 22,
        'comment_count': 11,
        'view_count': 12000,
        'is_liked': False,
        'is_favorited': False,
        'created_at': '2026-10-21T03:30:00Z',
    },
    {
        'id': 8,
        'post_type': 'lost_found',
        'category': '寻物失领',
        'content': '捡到一串校园钥匙，带小熊挂件\n在三教二楼自习室拾得，已交至保卫处前台。',
        'images': [],
        'price': None,
        'status': 1,
        'is_pinned': False,
        'is_featured': False,
        'user': {'nickname': '热心校友', 'avatar_url': None},
        'like_count': 3,
        'comment_count': 3,
        'view_count': 950,
        'is_liked': False,
        'is_favorited': False,
        'created_at': '2026-10-21T03:00:00Z',
    },
    {
        'id': 9,
        'post_type': 'general',
        'category': '校园生活',
        'content': '摄影协会秋季银杏摄影展征稿\n记录校园金秋最美瞬间，入选作品将印制成官方明信片。',
        'images': [],
        'price': None,
        'status': 1,
        'is_pinned': False,
        'is_featured': False,
        'user': {'nickname': '摄影协会', 'avatar_url': None},
        'like_count': 8,
        'comment_count': 5,
        'view_count': 1400,
        'is_liked': False,
        'is_favorited': False,
        'created_at': '2026-10-21T02:00:00Z',
    },
    {
        'id': 10,
        'post_type': 'general',
        'category': '校园生活',
        'content': '毕业租房避坑指南，学长学姐真实体验\n关于押金退还、中介合同、水电物业费的实用避坑提醒。',
        'images': [],
        'price': None,
        'status': 1,
        'is_pinned': False,
        'is_featured': False,
        'user': {'nickname': '职场学姐', 'avatar_url': None},
        'like_count': 14,
        'comment_count': 9,
        'view_count': 5600,
        'is_liked': False,
        'is_favorited': False,
        'created_at': '2026-10-21T01:00:00Z',
    },
]

FEED_POSTS_FIXTURE = [
    {
        'id': 101,
        'post_type': 'general',
        'content': '今天南湖边上的晚霞真美！\n有人一起夜跑吗？',
        'created_at': '2026-10-21T08:00:00Z',
        'view_count': 120,
        'comment_count': 5,
        'like_count': 18,
        'images': [],
        'user': {'nickname': '晚霞同学', 'avatar_url': None},
    },
    {
        'id': 102,
        'post_type': 'lost_found',
        'content': '捡到校园卡一张，在三号教学楼201\n姓名张**，请失主联系。',
        'created_at': '2026-10-21T07:30:00Z',
        'view_count': 88,
        'comment_count': 2,
        'like_count': 4,
        'images': [],
        'user': {'nickname': '热心学长', 'avatar_url': None},
    },
]

SEARCH_RESULTS_FIXTURE = [
    {
        'id': 1,
        'post_type': 'general',
        'category': '学习考研',
        'content': '图书馆自习室预约新规则全面讨论与建议 #自习室# #期末周#\n大家觉得现在的自习室预约时间与签到规则合理吗？欢迎大家在评论区留下你的建议！',
        'images': [],
        'price': None,
        'status': 1,
        'is_pinned': False,
        'is_featured': True,
        'user': {'nickname': '自习达人（考研上岸版超长昵称测试）', 'avatar_url': None},
        'like_count': 15,
        'comment_count': 3,
        'view_count': 21000,
        'is_liked': False,
        'is_favorited': False,
        'created_at': '2026-10-21T08:00:00Z',
    },
    {
        'id': 3,
        'post_type': 'second_hand',
        'category': '二手',
        'content': '毕业甩卖：99新考研英语/政治真题全套 #二手#\n仅自提，附送复试专业课笔记。超长文字排版测试：https://schoolwall.example.edu.cn/very/long/unbroken/path/to/resource/test',
        'images': [],
        'price': 45.0,
        'status': 1,
        'is_pinned': False,
        'is_featured': False,
        'user': {'nickname': '考研上岸学长', 'avatar_url': None},
        'like_count': 4,
        'comment_count': 2,
        'view_count': 8600,
        'is_liked': False,
        'is_favorited': False,
        'created_at': '2026-10-21T06:00:00Z',
    },
]

DETAIL_POST_FIXTURE = {
    'id': 1,
    'post_type': 'general',
    'category': '学习考研',
    'content': '图书馆自习室预约新规则全面讨论与建议 #自习室# #期末周#\n大家觉得现在的自习室预约时间与签到规则合理吗？近期很多同学反馈早上7:30预约系统并发卡顿，并且部分自习室插座供电不稳定。建议校方增加超时未签到自动释放机制，同时设立静音研讨区与背诵区，方便考研考公同学备考。欢迎大家在评论区留下你的建议！\n超长排版边界测试链接：https://schoolwall.example.edu.cn/posts/detail/1/very-long-unbroken-slug-without-whitespace-should-not-overflow',
    'images': [
        '/static/icons/banner/book.svg',
    ],
    'price': None,
    'status': 1,
    'is_pinned': False,
    'is_featured': True,
    'view_count': 21000,
    'like_count': 15,
    'comment_count': 3,
    'is_liked': False,
    'is_favorited': False,
    'created_at': '2026-10-21T08:00:00Z',
    'updated_at': '2026-10-21T08:00:00Z',
    'contact_info': 'vx_study_mate_2026_super_long_contact_id_for_boundary_check',
    'contact_wechat': 'vx_study_mate_2026_super_long_contact_id_for_boundary_check',
    'user_id': 'u1001',
    'author': {
        'id': 1001,
        'nickname': '自习达人（考研上岸版超长昵称测试）',
        'avatar_url': None,
    },
    'user': {
        'id': 1001,
        'nickname': '自习达人（考研上岸版超长昵称测试）',
        'avatar_url': None,
    },
    'is_following': False,
    'is_reported': False,
}

COMMENTS_FIXTURE = [
    {
        'id': 501,
        'post_id': 1,
        'user_id': 'u2001',
        'content': '非常赞成！三楼南侧的插座经常接触不良，希望能集中检修一次。另外早八赶课的时候网络延迟确实比较大。',
        'user': {'nickname': '自习室常驻选手', 'avatar_url': None},
        'created_at': '2026-10-21T08:15:00Z',
    },
    {
        'id': 502,
        'post_id': 1,
        'user_id': 'u2002',
        'content': '另外建议预约违约三次以内给一次申诉机会，有时候临时有早八实验课真的赶不过去。',
        'user': {'nickname': '生科小李', 'avatar_url': None},
        'created_at': '2026-10-21T08:20:00Z',
    },
    {
        'id': 503,
        'post_id': 1,
        'user_id': 'u2003',
        'content': '支持楼主！已经向后勤与图书管理中心提交联名建议书了，大家一起加油冲刺期末！超长评论排版测试语句无空格长串abcdefghijklmnopqrstuvwxyz1234567890',
        'user': {'nickname': '研学会学长', 'avatar_url': None},
        'created_at': '2026-10-21T08:30:00Z',
    },
]

def handle_api(route):
    url = route.request.url
    if any(k in url for k in ['/auth/dev-login', '/auth/web-login', '/auth/login', '/user/profile']):
        route.fulfill(status=401, content_type='application/json', body=json.dumps({'code': 401, 'message': '未登录'}))
    elif '/user/checkin/status' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps({'code': 0, 'data': {'checked_in': False, 'continuous_days': 0}}))
    elif '/banners' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps({'code': 0, 'data': {'items': []}}))
    elif '/posts/hot' in url:
        limit = 10
        if '?' in url:
            parsed_query = urllib.parse.parse_qs(url.split('?', 1)[1])
            if 'limit' in parsed_query:
                try:
                    limit = int(parsed_query['limit'][0])
                except ValueError:
                    limit = 10
        items = HOT_POSTS_FIXTURE[:limit]
        route.fulfill(status=200, content_type='application/json', body=json.dumps({'code': 0, 'data': {'items': items}}))
    elif '/posts/search' in url:
        if any(k in url for k in ['%E6%97%A0%E7%BB%93%E6%9E%9C', '无结果', 'empty', 'notfound']):
            route.fulfill(status=200, content_type='application/json', body=json.dumps({'code': 0, 'data': {'items': [], 'total': 0, 'has_more': False}}))
        else:
            route.fulfill(status=200, content_type='application/json', body=json.dumps({'code': 0, 'data': {'items': SEARCH_RESULTS_FIXTURE, 'total': len(SEARCH_RESULTS_FIXTURE), 'has_more': False}}))
    elif '/posts/1/comments' in url or '/comments' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps({'code': 0, 'data': {'items': COMMENTS_FIXTURE, 'total': len(COMMENTS_FIXTURE), 'has_more': False}}))
    elif '/posts/1' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps({'code': 0, 'data': DETAIL_POST_FIXTURE}))
    elif '/posts' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps({'code': 0, 'data': {'items': FEED_POSTS_FIXTURE, 'total': 2}}))
    elif '/notification/unread' in url:
        route.fulfill(status=200, content_type='application/json', body=json.dumps({'code': 0, 'data': {'comment': 0, 'like': 0, 'favorite': 0, 'group': 0, 'moderation': 0}}))
    else:
        route.fulfill(status=200, content_type='application/json', body=json.dumps({'code': 0, 'data': {'items': []}}))


# ---- 共享布局/可读性断言工具（移动端与桌面/平板走查通用） ----
def assert_no_horizontal_overflow(page, page_name):
    metrics = page.evaluate('''() => {
        const doc = document.documentElement;
        const body = document.body;
        return {
            docScroll: doc.scrollWidth,
            docClient: doc.clientWidth,
            bodyScroll: body.scrollWidth,
            bodyClient: body.clientWidth,
            windowInner: window.innerWidth,
        };
    }''')
    overflow = metrics['docScroll'] > metrics['docClient'] + 2 or metrics['bodyScroll'] > metrics['bodyClient'] + 2
    assert not overflow, f"{page_name} 检测到横向溢出: {metrics}"
    print(f"   [布局安全] {page_name} 无横向溢出 (视口宽={metrics['windowInner']}px, 文档宽={metrics['docScroll']}px)")

def assert_bottom_bar_not_blocking(page, page_name):
    page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
    page.wait_for_timeout(400)
    check = page.evaluate('''() => {
        const lastContent = document.querySelector('.comment-no-more') || document.querySelector('.comment:last-child');
        const bar = document.querySelector('.comment-input-bar');
        if (!bar) return { ok: true, reason: 'no input bar' };
        const barRect = bar.getBoundingClientRect();
        if (!lastContent) return { ok: true, reason: 'no content' };
        const contentRect = lastContent.getBoundingClientRect();
        return {
            ok: contentRect.bottom <= barRect.top + 5,
            contentBottom: contentRect.bottom,
            barTop: barRect.top,
        };
    }''')
    assert check['ok'], f"{page_name} 底部固定输入栏遮挡关键内容: {check}"
    print(f"   [留白安全] {page_name} 底部输入栏留白正常: 评论内容底边={check.get('contentBottom')}px, 输入栏顶边={check.get('barTop')}px")

def parse_css_rgb(color_str):
    import re
    m = re.search(r'rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', color_str)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    if color_str.startswith('#'):
        h = color_str.lstrip('#')
        if len(h) == 6:
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        if len(h) == 3:
            return int(h[0]*2, 16), int(h[1]*2, 16), int(h[2]*2, 16)
    raise ValueError(f"Cannot parse CSS color: {color_str}")

def calculate_wcag_contrast(fg_str, bg_str):
    fg_rgb = parse_css_rgb(fg_str)
    bg_rgb = parse_css_rgb(bg_str)
    def channel_luminance(c):
        s = c / 255.0
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4
    def relative_luminance(rgb):
        return 0.2126 * channel_luminance(rgb[0]) + 0.7152 * channel_luminance(rgb[1]) + 0.0722 * channel_luminance(rgb[2])
    l1 = relative_luminance(fg_rgb)
    l2 = relative_luminance(bg_rgb)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


# ---------------------------------------------------------------------------
# 元素实际对比度读取（前景/背景都做 alpha 合成）
# 用于把「写死令牌色值」的断言升级为「对比度达标」断言：
# 令牌值调整时断言依然成立，且真正约束的是可读性而非某个 hex。
# ---------------------------------------------------------------------------
_READ_CONTRAST_JS = '''(selector) => {
    const parse = (s) => {
        const m = String(s).match(/rgba?\\(([^)]+)\\)/);
        if (!m) return null;
        const p = m[1].split(',').map(x => parseFloat(x));
        return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
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
    const el = document.querySelector(selector);
    if (!el) return null;
    const fg = parse(getComputedStyle(el).color);
    if (!fg) return null;
    // 向上合成背景色（跳过透明层），遇到不透明层即停
    const stack = [];
    let node = el;
    while (node && node.nodeType === 1) {
        const c = parse(getComputedStyle(node).backgroundColor);
        if (c && c.a > 0) { stack.push(c); if (c.a >= 0.999) break; }
        node = node.parentElement;
    }
    let bg = { r: 255, g: 255, b: 255, a: 1 };
    for (let i = stack.length - 1; i >= 0; i--) bg = over(stack[i], bg);
    const effFg = fg.a < 1 ? over(fg, bg) : fg;
    const l1 = lum(effFg), l2 = lum(bg);
    const hi = Math.max(l1, l2), lo = Math.min(l1, l2);
    const rgb = (c) => `rgb(${Math.round(c.r)}, ${Math.round(c.g)}, ${Math.round(c.b)})`;
    return {
        fg: rgb(effFg), bg: rgb(bg),
        ratio: Math.round(((hi + 0.05) / (lo + 0.05)) * 100) / 100,
        fontSize: parseFloat(getComputedStyle(el).fontSize),
    };
}'''


def read_element_contrast(page, selector):
    """读取元素实际前景/背景（已 alpha 合成）与 WCAG 对比度。元素不存在返回 None。"""
    return page.evaluate(_READ_CONTRAST_JS, selector)


def assert_element_contrast(page, selector, min_ratio, label, page_name='页面'):
    """断言元素实际对比度不低于 min_ratio（默认按正文 4.5:1）。"""
    data = read_element_contrast(page, selector)
    assert data is not None, f"{page_name} {label}: 找不到元素 {selector}"
    assert data['ratio'] >= min_ratio, (
        f"{page_name} {label} 对比度不足 {min_ratio}:1 (实际 {data['ratio']}:1, "
        f"前景 {data['fg']}, 背景 {data['bg']})"
    )
    print(f"   [对比度] {page_name} {label}: {data['fg']} on {data['bg']} = {data['ratio']}:1 (>= {min_ratio}:1)")
    return data

_READ_TOKEN_COLOR_JS = """
({ sel, tok }) => {
  const el = document.querySelector(sel);
  if (!el) return null;
  const raw = getComputedStyle(el).getPropertyValue(tok).trim();
  if (!raw) return null;
  const probe = document.createElement('span');
  probe.style.color = raw;
  document.body.appendChild(probe);
  const rgb = getComputedStyle(probe).color;
  probe.remove();
  return rgb;
}"""


def read_token_color(page, selector, token='--text-1'):
    """读取元素所在上下文中某设计令牌的实际计算色（换品牌同样成立）。"""
    return page.evaluate(_READ_TOKEN_COLOR_JS, {'sel': selector, 'tok': token})


def assert_token_color(page, selector, token='--text-1', label='', page_name='页面'):
    """断言元素颜色等于设计令牌的计算值：令牌改了断言不用改。"""
    expected = read_token_color(page, selector, token)
    assert expected, f"{page_name} {label}: 取不到令牌 {token}（元素 {selector}）"
    actual = page.locator(selector).first.evaluate('el => getComputedStyle(el).color')
    assert actual == expected, (
        f"{page_name} {label}: 应使用令牌 {token}({expected})，实际 {actual}"
    )
    print(f"   [令牌色] {page_name} {label}: {token}={expected}")
    return actual


_READ_TOKEN_BACKGROUND_JS = """
({ sel, tok }) => {
  const el = document.querySelector(sel);
  if (!el) return null;
  const raw = getComputedStyle(el).getPropertyValue(tok).trim();
  if (!raw) return null;
  const probe = document.createElement('span');
  probe.style.backgroundColor = raw;
  document.body.appendChild(probe);
  const rgb = getComputedStyle(probe).backgroundColor;
  probe.remove();
  return rgb;
}"""


def read_token_background(page, selector, token='--pill-bg'):
    """读取某设计令牌作为背景色时的实际计算值（换品牌同样成立）。"""
    return page.evaluate(_READ_TOKEN_BACKGROUND_JS, {'sel': selector, 'tok': token})


def assert_token_background(page, selector, token='--pill-bg', label='', page_name='页面'):
    """断言元素底色等于设计令牌的计算值：令牌改了断言不用改。

    底色与文字色是两回事，不能用 assert_token_color 断言。
    """
    expected = read_token_background(page, selector, token)
    assert expected, f"{page_name} {label}: 取不到令牌 {token}（元素 {selector}）"
    actual = page.locator(selector).first.evaluate('el => getComputedStyle(el).backgroundColor')
    assert actual == expected, (
        f"{page_name} {label}: 底色应使用令牌 {token}({expected})，实际 {actual}"
    )
    print(f"   [令牌底色] {page_name} {label}: {token}={expected}")
    return actual

