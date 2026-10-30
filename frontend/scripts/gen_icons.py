#!/usr/bin/env python3
"""
SchoolWall 学生端 SVG 图标库生成器

为什么需要它：
  1. emoji 在不同系统/微信里字形不一致（emoji 字体缺失时退化成黑白方块），
     且无法跟随主题变色；SVG 线条图标在 H5 / mp-weixin / App 三端渲染一致。
  2. mp-weixin 不支持 <svg> 标签，但支持 <image> 引用 .svg，
     因此统一走 static/icons 下的 .svg 资源 + <image mode="aspectFit">。

图标规范（与既有 settings/feed/tabbar 图标保持一致）：
  - 画布 24×24 viewBox，线条图标 fill="none" + stroke + stroke-width 1.8
  - 描边圆头圆角（stroke-linecap="round" stroke-linejoin="round"）
  - 颜色令牌（与 App.vue 设计令牌一一对应）：
      default  #666666  中性（浅底 5.7:1 / 深底 3.2:1，两端都达 WCAG 非文本对比度）
      primary  #1d9bf0  X 品牌蓝（--primary）
      inverse  #ffffff  品牌色/渐变底上的图标（--text-inverse）
      danger   #c93a3a  语义红
      like     #f918b6  X 点赞粉（--like，白底 3.6:1）
      favorite #b8860b  收藏深金（白底 3.4:1，达非文本 3:1）

「激活态」图标（heart-on / bookmark-on / star-on）用 base_tone 指定自身色，
其余图标一律 default 为中性灰、需要强调时用 tone 变体。

用法：python3 frontend/scripts/gen_icons.py
生成：frontend/src/static/icons/<分组>/<名称>.svg
"""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ICON_ROOT = os.path.join(ROOT, 'frontend', 'src', 'static', 'icons')

TONES = {
    'default': '#666666',
    'primary': '#1d9bf0',
    'inverse': '#ffffff',
    'danger': '#c93a3a',
    'like': '#f918b6',
    'favorite': '#b8860b',
}

# ---------------------------------------------------------------- 图标几何
# 每项：分组 -> 名称 -> (路径内容, 是否填充式, 基色令牌)
# 填充式图标（fill 型）路径不含 fill="none"，直接用 fill 着色。
# 基色令牌缺省为 default；激活态图标（点赞/收藏/签到）显式指定自身强调色。
ICONS = {
    'common': {
        # —— 方向与导航 ——
        'arrow-right': ('<polyline points="9 18 15 12 9 6"/>', False),
        'arrow-down': ('<polyline points="6 9 12 15 18 9"/>', False),
        'arrow-up': ('<polyline points="18 15 12 9 6 15"/>', False),
        'back': ('<polyline points="15 18 9 12 15 6"/>', False),
        'share': ('<line x1="17" y1="7" x2="7" y2="17"/><polyline points="7 7 17 7 17 17"/>', False),
        'up': ('<line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/>', False),
        'external': ('<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>'
                     '<polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>', False),
        # —— 操作 ——
        'plus': ('<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>', False),
        'publish': ('<rect x="3" y="3" width="18" height="18" rx="4"/><line x1="12" y1="8" x2="12" y2="16"/>'
                    '<line x1="8" y1="12" x2="16" y2="12"/>', False),
        'check': ('<polyline points="20 6 9 17 4 12"/>', False),
        'search': ('<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>', False),
        'send': ('<line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>', False),
        'refresh': ('<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>'
                    '<path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>', False),
        # —— 内容 ——
        'location': ('<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>', False),
        'pin': ('<path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>', False),
        'clock': ('<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>', False),
        'book': ('<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>', False),
        'money': ('<line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>', False),
        'image': ('<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/>'
                  '<polyline points="21 15 16 10 5 21"/>', False),
        'camera': ('<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>'
                   '<circle cx="12" cy="13" r="4"/>', False),
        'layers': ('<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/>'
                   '<polyline points="2 12 12 17 22 12"/>', False),
        'list': ('<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/>'
                 '<line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/>'
                 '<line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>', False),
        'mic': ('<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/>'
                '<line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/>', False),
        'emoji': ('<circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/>'
                  '<line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/>', False),
        # —— 互动（几何与既有 feed/ 图标一致，收编进生成器以便出色调变体）——
        'heart': ('<path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09'
                  'C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>', False),
        'heart-on': ('<path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09'
                     'C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>', True, 'like'),
        'comment': ('<path d="M4 5h16a1.5 1.5 0 0 1 1.5 1.5v9a1.5 1.5 0 0 1-1.5 1.5h-8l-5 4v-4H4a1.5 1.5 0 0 1-1.5-1.5v-9A1.5 1.5 0 0 1 4 5z"/>', False),
        'bookmark': ('<path d="M6 3h12a1 1 0 0 1 1 1v17l-7-4.5L5 21V4a1 1 0 0 1 1-1z"/>', False),
        'bookmark-on': ('<path d="M6 3h12a1 1 0 0 1 1 1v17l-7-4.5L5 21V4a1 1 0 0 1 1-1z"/>', True, 'favorite'),
        'eye': ('<path d="M5 20v-5"/><path d="M12 20V9"/><path d="M19 20V4"/>', False),
        'note': ('<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>'
                 '<line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>', False),
        'shield': ('<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>', False),
        'eye-open': ('<path d="M1.8 12S5.5 5.5 12 5.5 22.2 12 22.2 12 18.5 18.5 12 18.5 1.8 12 1.8 12z"/>'
                     '<circle cx="12" cy="12" r="3"/>', False),
        'eye-off': ('<path d="M9.6 5.7A9.9 9.9 0 0 1 12 5.5c6.5 0 10.2 6.5 10.2 6.5a17.8 17.8 0 0 1-3.1 3.9"/>'
                    '<path d="M6.2 7.8A17.6 17.6 0 0 0 1.8 12S5.5 18.5 12 18.5a9.6 9.6 0 0 0 4-.85"/>'
                    '<path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/><line x1="3" y1="3" x2="21" y2="21"/>', False),
        # —— 激活态（自身即强调色）——
        'star-on': ('<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
                    True, 'favorite'),
        'hot-on': ('<path d="M12 22a7 7 0 0 0 7-7c0-4-3-6-4.5-9.5C13 8 11 8 11 11c0 1.5-1 2.5-2 3-1.2.6-2 1.8-2 3.5a5 5 0 0 0 5 4.5z"/>'
                   '<path d="M12 22a3.5 3.5 0 0 0 3.5-3.5c0-1.5-1-2.5-2-3.5-.6 1-1.5 1.5-2.5 1.5"/>', True, 'primary'),
        # —— 更多/关闭 ——
        'more': ('<circle cx="5" cy="12" r="1.7"/><circle cx="12" cy="12" r="1.7"/><circle cx="19" cy="12" r="1.7"/>', True),
        'close': ('<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>', False),
        # —— 业务语义 ——
        'campus': ('<path d="M3 21h18"/><path d="M5 21V8.5L12 3l7 5.5V21"/><path d="M9.5 21v-6h5v6"/>'
                   '<line x1="9" y1="11" x2="9.01" y2="11"/><line x1="12" y1="11" x2="12.01" y2="11"/>'
                   '<line x1="15" y1="11" x2="15.01" y2="11"/>', False),
        'cart': ('<circle cx="9" cy="20" r="1.5"/><circle cx="18" cy="20" r="1.5"/>'
                 '<path d="M2 3h2.6l2.6 11.6a2 2 0 0 0 2 1.6h7.6a2 2 0 0 0 1.9-1.4L21 7H5.5"/>', False),
        'ball': ('<circle cx="12" cy="12" r="9"/><line x1="12" y1="3" x2="12" y2="21"/>'
                 '<path d="M5.2 6.4c3.4 1.6 5.4 4 6.8 6.4 1.4 2.4 3.4 4.8 6.8 6.4"/>'
                 '<path d="M5.2 17.6c3.4-1.6 5.4-4 6.8-6.4 1.4-2.4 3.4-4.8 6.8-6.4"/>', False),
        'hot': ('<path d="M12 22a7 7 0 0 0 7-7c0-4-3-6-4.5-9.5C13 8 11 8 11 11c0 1.5-1 2.5-2 3-1.2.6-2 1.8-2 3.5a5 5 0 0 0 5 4.5z"/>'
                '<path d="M12 22a3.5 3.5 0 0 0 3.5-3.5c0-1.5-1-2.5-2-3.5-.6 1-1.5 1.5-2.5 1.5"/>', False),
        'notice': ('<path d="M3 11l18-5v12L3 14v-3z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/>', False),
        'help': ('<circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>', False),
        'stats': ('<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>', False),
        'verify': ('<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/>', False),
        'signin': ('<path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/>', False),
        'ufo': ('<path d="M12 3c4.4 0 8 3.4 8 6.5S16.4 16 12 16 4 12.6 4 9.5 7.6 3 12 3z"/>'
                '<path d="M8.5 9.5h.01M12 9.5h.01M15.5 9.5h.01"/><path d="M4 19c2-2 4 2 8 2s6-4 8-2"/>', False),
        # —— 导航与身份 ——
        'home': ('<path d="M3 9.5L12 3l9 6.5V20a1.5 1.5 0 0 1-1.5 1.5H4.5A1.5 1.5 0 0 1 3 20V9.5z"/><path d="M9 21V12h6v9"/>', False),
        'group': ('<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>'
                  '<path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>', False),
        'message': ('<path d="M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"/><polyline points="22,6 12,13 2,6"/>', False),
        'mine': ('<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>', False),
        'star': ('<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>', False),
    },
    'state': {
        'inbox': ('<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/>'
                  '<path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>', False),
        'ice': ('<line x1="12" y1="2" x2="12" y2="22"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/>'
                '<line x1="19.07" y1="4.93" x2="4.93" y2="19.07"/><line x1="2" y1="12" x2="22" y2="12"/>'
                '<polyline points="9 5 12 7 15 5"/><polyline points="9 19 12 17 15 19"/>'
                '<polyline points="5 9 7 12 5 15"/><polyline points="19 9 17 12 19 15"/>', False),
        'mail-heart': ('<path d="M4 4h16a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"/>'
                       '<polyline points="22,6 12,13 2,6"/><path d="M8.5 20s-3.5-2.2-3.5-4.4A2 2 0 0 1 8.5 14a2 2 0 0 1 3.5 1.6c0 2.2-3.5 4.4-3.5 4.4z"/>', False),
        'desktop': ('<rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/>'
                    '<line x1="12" y1="17" x2="12" y2="21"/>', False),
        'palette': ('<path d="M12 2a10 10 0 1 0 0 20c1.4 0 2-1 2-2 0-1.6-1.6-1.6-1.6-3 0-1.2 1-2 2.2-2H17c3 0 5-2.2 5-5 0-4.4-4.8-8-10-8z"/>'
                    '<circle cx="7.5" cy="10.5" r="1"/><circle cx="12" cy="7.5" r="1"/>'
                    '<circle cx="16.5" cy="10.5" r="1"/>', False),
        'party': ('<path d="M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/>'
                  '<line x1="4" y1="3" x2="5" y2="5"/><line x1="19" y1="3" x2="20" y2="5"/>'
                  '<line x1="21" y1="8" x2="23" y2="7"/>', False),
        'tree': ('<path d="M12 22v-7"/><path d="M12 15l-5-3h3l-4-5h4L7 3h10l-3 4h4l-4 5h3z"/>', False),
        'crown': ('<path d="M3 7l3.5 4L12 4l5.5 7L21 7l-1.6 10H4.6z"/><line x1="4.6" y1="20" x2="19.4" y2="20"/>', False),
        'sparkle': ('<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/>'
                    '<path d="M18.5 15.5l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z"/>', False),
        'briefcase': ('<rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>', False),
    },
    'party': {
        'star': ('<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>', False),
        'book': ('<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>', False),
        'film': ('<rect x="2" y="4" width="20" height="16" rx="2"/><line x1="7" y1="4" x2="7" y2="20"/>'
                 '<line x1="17" y1="4" x2="17" y2="20"/><line x1="2" y1="12" x2="22" y2="12"/>'
                 '<line x1="2" y1="8" x2="7" y2="8"/><line x1="2" y1="16" x2="7" y2="16"/>'
                 '<line x1="17" y1="8" x2="22" y2="8"/><line x1="17" y1="16" x2="22" y2="16"/>', False),
        'dining': ('<path d="M6 2v7a3 3 0 0 0 6 0V2"/><line x1="6" y1="9" x2="6" y2="22"/>'
                   '<line x1="12" y1="9" x2="12" y2="22"/><line x1="18" y1="2" x2="18" y2="22"/>'
                   '<path d="M18 2c2 2 3 5 3 7h-3"/>', False),
        'car': ('<path d="M5 17h14"/><path d="M6.5 17a1.5 1.5 0 0 1-1.5-1.5v-2l1.6-4.6A2 2 0 0 1 8.5 7.5h7a2 2 0 0 1 1.9 1.4L19 13.5v2'
                'a1.5 1.5 0 0 1-1.5 1.5z"/><circle cx="7.5" cy="17.5" r="2"/><circle cx="16.5" cy="17.5" r="2"/>', False),
        'shopping': ('<path d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/>'
                     '<path d="M16 10a4 4 0 0 1-8 0"/>', False),
        'running': ('<circle cx="15.5" cy="4.5" r="2"/><path d="M12.5 21l-2-6 3-3-1-4-4 2-2 3"/>'
                    '<path d="M9 15l-3 1-2 4"/><path d="M13.5 8l4 2 3 1"/>', False),
        'game': ('<rect x="2" y="7" width="20" height="11" rx="4"/><line x1="7" y1="12.5" x2="10" y2="12.5"/>'
                 '<line x1="8.5" y1="11" x2="8.5" y2="14"/><line x1="15.5" y1="12" x2="15.51" y2="12"/>'
                 '<line x1="18" y1="14" x2="18.01" y2="14"/>', False),
        'palm': ('<path d="M12 22V11"/><path d="M12 11c0-3-2.5-5-5.5-5C4 6 3 8 3 8s2 1 4 1"/>'
                 '<path d="M12 11c0-3 2.5-5 5.5-5C20 6 21 8 21 8s-2 1-4 1"/>'
                 '<path d="M12 11c-1.5-2.5-1-5 1-6.5 2 1.5 2.5 4 1 6.5"/>', False),
        'gear': ('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33'
                 ' 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06'
                 'a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06'
                 'a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06'
                 'a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>', False),
    },
    'publish': {
        'general': ('<path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7'
                    'a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8z"/>', False),
        'second-hand': ('<path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/>'
                        '<line x1="7" y1="7" x2="7.01" y2="7"/>', False),
        'lost': ('<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>', False),
        'carpool': ('<path d="M5 17h14"/><path d="M6.5 17a1.5 1.5 0 0 1-1.5-1.5v-2l1.6-4.6A2 2 0 0 1 8.5 7.5h7a2 2 0 0 1 1.9 1.4L19 13.5v2'
                    'a1.5 1.5 0 0 1-1.5 1.5z"/><circle cx="7.5" cy="17.5" r="2"/><circle cx="16.5" cy="17.5" r="2"/>', False),
    },
}

# 需要品牌蓝/反白/危险色的图标（按分组给出 tone 列表）
TONED = {
    'common': {
        'primary': ['hot', 'notice', 'verify', 'stats', 'publish', 'search', 'location',
                    'signin', 'help', 'star', 'home', 'group', 'message', 'mine', 'book',
                    'money', 'image', 'camera', 'clock', 'pin', 'send', 'share', 'refresh',
                    'arrow-right', 'arrow-down', 'arrow-up', 'back', 'up', 'external',
                    'plus', 'check', 'mic', 'emoji', 'layers', 'list', 'ufo',
                    'heart', 'comment', 'bookmark', 'eye', 'note', 'shield',
                    'campus', 'cart', 'ball', 'more', 'close'],
        'inverse': ['heart-on', 'bookmark-on', 'star-on', 'hot-on',
                    'group', 'plus', 'notice', 'shield', 'comment', 'eye', 'close',
                    'heart', 'bookmark', 'check', 'location', 'clock', 'star', 'more',
                    'campus', 'cart', 'ball', 'note', 'publish', 'send', 'share',
                    'up', 'camera', 'arrow-right', 'arrow-up', 'eye-open', 'eye-off'],
        'danger': [],
    },
    'state': {
        'primary': ['inbox', 'ice', 'mail-heart', 'desktop', 'palette', 'party', 'tree', 'crown', 'sparkle'],
        'inverse': ['crown', 'party', 'palette', 'mail-heart', 'desktop'],
    },
    'party': {
        'primary': ['star', 'book', 'film', 'dining', 'car', 'shopping', 'running', 'game', 'palm', 'gear'],
    },
    'publish': {
        'primary': ['general', 'second-hand', 'lost', 'carpool'],
    },
}

# 复用既有图标的语义名 -> 既有文件（默认色）。既有文件没有 tone 变体，
# 因此这些语义名只提供 default；需要品牌色的场景用 ICONS 里同名的图标。
LEGACY = {
    'trash': '/static/icons/settings/trash.svg',
    'settings': '/static/icons/settings/gear.svg',
    'invite': '/static/icons/settings/gift.svg',
    'contact': '/static/icons/settings/phone.svg',
    'about': '/static/icons/settings/info.svg',
    'doc': '/static/icons/settings/doc.svg',
    'link': '/static/icons/settings/link.svg',
    'edit': '/static/icons/settings/doc.svg',
    'banner-grad': '/static/icons/banner/grad.svg',
    'banner-guide': '/static/icons/banner/guide.svg',
    'banner-market': '/static/icons/banner/market.svg',
    'banner-book': '/static/icons/banner/book.svg',
}

LINE_TEMPLATE = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
                  'stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
                  '{body}</svg>\n')
FILL_TEMPLATE = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="{color}">'
                 '{body}</svg>\n')

# 分组前缀：state/party/publish 用前缀避免语义名冲突
GROUP_PREFIX = {'common': '', 'state': 'state-', 'party': 'party-', 'publish': 'publish-'}


def flat_name(group: str, name: str) -> str:
    return f'{GROUP_PREFIX[group]}{name}'


def norm(entry) -> tuple[str, bool, str]:
    """图标条目 -> (路径内容, 是否填充式, 基色令牌)。基色缺省为 default。"""
    if len(entry) == 3:
        body, filled, base = entry
    else:
        body, filled = entry
        base = 'default'
    return body, filled, base


def write_icon(group: str, name: str, body: str, filled: bool, color: str, suffix: str):
    tpl = FILL_TEMPLATE if filled else LINE_TEMPLATE
    path = os.path.join(ICON_ROOT, group, f'{name}{suffix}.svg')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(tpl.format(color=color, body=body))
    return path


def main():
    written = []
    registry: dict[str, str] = {}
    tones: dict[str, dict[str, str]] = {}

    for group, icons in ICONS.items():
        for name, entry in icons.items():
            body, filled, base = norm(entry)
            written.append(write_icon(group, name, body, filled, TONES[base], ''))
            registry[flat_name(group, name)] = f'/static/icons/{group}/{name}.svg'

    for group, tone_map in TONED.items():
        for tone, names in tone_map.items():
            for name in names:
                if name not in ICONS.get(group, {}):
                    continue
                body, filled, base = norm(ICONS[group][name])
                if tone == base:
                    continue  # 基色即该 tone，文件已由上面写出
                written.append(write_icon(group, name, body, filled, TONES[tone], f'-{tone}'))
                key = flat_name(group, name)
                tones.setdefault(key, {})[tone] = f'/static/icons/{group}/{name}-{tone}.svg'

    # 复用既有图标：不重复生成文件，注册表直接指向老资源
    for key, path in LEGACY.items():
        registry[key] = path

    # 清掉上一轮生成、但已从图标集移除的冗余文件
    expected = {os.path.relpath(p, ICON_ROOT).replace(os.sep, '/') for p in written}
    for group in ICONS:
        gdir = os.path.join(ICON_ROOT, group)
        if not os.path.isdir(gdir):
            continue
        for fn in os.listdir(gdir):
            rel = f'{group}/{fn}'
            if rel not in expected:
                os.remove(os.path.join(gdir, fn))
                print('  清理冗余:', rel)

    # 输出 TypeScript 注册表
    lines = [
        '/**',
        ' * 图标注册表 —— 由 frontend/scripts/gen_icons.py 生成，请勿手改。',
        ' *',
        ' * 语义名 -> SVG 资源路径；tone 变体（品牌蓝/反白/危险色）见 ICON_TONES。',
        ' */',
        'export const ICONS: Record<string, string> = {',
    ]
    for key in sorted(registry):
        lines.append(f"  '{key}': '{registry[key]}',")
    lines.append('}')
    lines.append('')
    lines.append('/** 语义名 -> tone -> 资源路径（仅列出实际存在的变体） */')
    lines.append('export const ICON_TONES: Record<string, Record<string, string>> = {')
    for key in sorted(tones):
        inner = ', '.join(f"'{t}': '{p}'" for t, p in sorted(tones[key].items()))
        lines.append(f"  '{key}': {{ {inner} }},")
    lines.append('}')
    lines.append('')
    reg_path = os.path.join(ROOT, 'frontend', 'src', 'utils', 'icons.ts')
    with open(reg_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f'生成 {len(written)} 个 SVG -> {ICON_ROOT}')
    print(f'注册表 {len(registry)} 个语义名 -> {reg_path}')


if __name__ == '__main__':
    main()
