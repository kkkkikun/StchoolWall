/**
 * Mock 数据 —— 提取自 ref/ 设计稿样例，供前端独立预览。
 * 后端完善后逐步替换为真实 API 调用。
 */
import type {
  AdBanner,
  Feed,
  HotPost,
  MenuItem,
  MessageCategory,
  MessageItem,
  MineMenu,
  MineStats,
  MineUser,
  PartyCategory,
  PartyItem,
} from '@/types/mock'
import { ICONS } from './icons'

/* ============ 首页 ============ */

/** 首页吸顶分类 Tab */
export const HOME_TABS = ['推荐', '关注', '校园生活', '学习考研', '情感树洞', '美食探店'] as const

/** 十大热帖 */
export const HOT_POSTS: HotPost[] = [
  { id: 101, rank: 1, title: '求助！大二绩点2.6还有救吗', isHot: true, reads: '5.2万阅读' },
  { id: 102, rank: 2, title: '期末周自习室推荐！附空位情况', isHot: false, reads: '3.8万阅读' },
  { id: 103, rank: 3, title: '学校北门新开的奶茶店也太好喝了吧', isHot: false, reads: '2.6万阅读' },
  { id: 104, rank: 4, title: '四六级冲刺打卡第 N 天，组队互相监督', isHot: false, reads: '1.9万阅读' },
]

/** 帖子分类（金刚区固定分类法，发布/过滤共用） */
export const POST_CATEGORIES = [
  '广场', '二手', '失物',
] as const

/** 金刚区 10 宫格（点击按 category 过滤信息流；「更多分类」跳搜索） */
export const MENU_ITEMS: MenuItem[] = [
  { name: '校园广场', icon: ICONS['campus'] },
  { name: '二手市场', icon: ICONS['cart'], badge: '新' },
  { name: '失物招领', icon: ICONS['search'] },
  { name: '兼职实习', icon: ICONS['state-briefcase'] },
  { name: '表白墙', icon: ICONS['state-mail-heart'] },
  { name: '一起自习', icon: ICONS['book'] },
  { name: '兴趣社团', icon: ICONS['state-palette'] },
  { name: '校园活动', icon: ICONS['state-party'] },
  { name: '树洞倾诉', icon: ICONS['state-tree'] },
  { name: '更多分类', icon: ICONS['more'], badge: '全部' },
]

/** 首页广告位轮播 */
export const AD_BANNERS: AdBanner[] = [
  {
    id: 1,
    icon: ICONS['banner-grad'],
    title: '毕业季 · 鄂应专属',
    desc: '留下你的校园回忆，赢毕业礼包',
    tag: '活动',
    bg: 'linear-gradient(135deg, #ef8a97, #f6b8c0)',
  },
  {
    id: 2,
    icon: ICONS['banner-guide'],
    title: '迎新季 · 新生攻略',
    desc: '一键获取校园生存指南',
    tag: '热门',
    bg: 'linear-gradient(135deg, #667eea, #764ba2)',
  },
  {
    id: 3,
    icon: ICONS['banner-market'],
    title: '跳蚤集市 · 闲置流转',
    desc: '毕业季二手好物，低价淘',
    tag: '集市',
    bg: 'linear-gradient(135deg, #11998e, #38ef7d)',
  },
  {
    id: 4,
    icon: ICONS['banner-book'],
    title: '期末互助 · 真题共享',
    desc: '组队复习，资料一键互传',
    tag: '学习',
    bg: 'linear-gradient(135deg, #2193b0, #6dd5ed)',
  },
]

/** 首页信息流 */
export const HOME_FEEDS: Feed[] = [
  {
    id: 10001,
    username: '小熊软糖',
    avatar: ICONS['mine'],
    avatarColor: '#ffd591',
    verified: true,
    time: '1分钟前',
    content: '家人们，山上食堂有哪些好吃的，急！\n本人干饭人一枚，最近想换换口味，求推荐不踩雷的窗口～谢谢大家啦！',
    tag: '校园生活',
    images: 0,
  },
  {
    id: 10002,
    username: '鄂小鹰0007',
    avatar: ICONS['mine'],
    avatarColor: '#adc6ff',
    verified: false,
    time: '12分钟前',
    content: '期末周图书馆几点开门？听说现在占座很卷，有经验的同学说说。',
    tag: '学习考研',
  },
  {
    id: 10003,
    username: '最爱吃兽奶',
    avatar: ICONS['mine'],
    avatarColor: '#ffe7ba',
    verified: true,
    time: '半小时前',
    content: '出九成新高数教材 + 习题全解，自提东校区，10r 包邮可谈。',
    tag: '二手交易',
    images: 2,
  },
  {
    id: 10004,
    username: '匿名树洞',
    avatar: ICONS['state-tree'],
    avatarColor: '#d9f7be',
    verified: false,
    time: '1小时前',
    content: '最近压力好大，有没有人也是边考研边实习的，你们怎么平衡的……',
    tag: '情感树洞',
  },
]

/* ============ 组局 ============ */

/** 组局统计人数 */
export const GROUP_TOTAL_USER = 6693

/** 组局分类筛选 */
export const PARTY_CATEGORIES: PartyCategory[] = [
  { id: 0, icon: ICONS['party-star'], name: '有空位', count: 128 },
  { id: 1, icon: ICONS['party-book'], name: '自习', count: 86 },
  { id: 2, icon: ICONS['party-film'], name: '电影', count: 112 },
  { id: 3, icon: ICONS['party-dining'], name: '聚餐', count: 98 },
  { id: 4, icon: ICONS['party-car'], name: '拼车', count: 76 },
  { id: 5, icon: ICONS['party-shopping'], name: '拼单', count: 64 },
  { id: 6, icon: ICONS['party-running'], name: '运动', count: 142 },
  { id: 7, icon: ICONS['party-game'], name: '游戏', count: 95 },
  { id: 8, icon: ICONS['party-palm'], name: '旅行', count: 39 },
  { id: 9, icon: ICONS['party-gear'], name: '其他', count: 63 },
]

/** 组局/拼单列表 */
export const PARTY_LIST: PartyItem[] = [
  {
    id: 2001,
    type: '组局',
    title: '大学生创新创业大赛来带！想找一个靠谱团队一起冲大创，一起认真做项目！',
    username: '小熊软糖',
    avatar: ICONS['mine'],
    avatarColor: '#ffd591',
    date: '6-1',
    joined: 6,
    total: 8,
  },
  {
    id: 2002,
    type: '组局',
    title: '今晚有人打半场篮球吗？',
    username: '最爱吃兽奶',
    avatar: ICONS['mine'],
    avatarColor: '#ffe7ba',
    date: '6-1',
    joined: 3,
    total: 10,
    decorIcon: ICONS['ball'],
  },
  {
    id: 2003,
    type: '组局',
    title: '晚上有没有人来操场玩狼人杀？',
    username: '最爱吃兽奶',
    avatar: ICONS['mine'],
    avatarColor: '#ffe7ba',
    date: '6-1',
    joined: 5,
    total: 8,
    decorIcon: ICONS['party-game'],
  },
  {
    id: 2004,
    type: '拼单',
    title: '打车去东胜万达，下午2点出发，还差2人，车费AA',
    username: '小熊软糖',
    avatar: ICONS['mine'],
    avatarColor: '#ffd591',
    date: '6-1',
    joined: 2,
    total: 4,
    decorIcon: ICONS['party-car'],
  },
]

/* ============ 消息 ============ */

/** 消息 4 分类 */
export const MESSAGE_CATEGORIES: MessageCategory[] = [
  { type: 'comment', name: '评论', icon: ICONS['comment'], colorClass: 'blue', unreadCount: 0 },
  { type: 'like', name: '赞', icon: ICONS['heart'], colorClass: 'pink', unreadCount: 0 },
  { type: 'party', name: '组局', icon: ICONS['group'], colorClass: 'yellow', unreadCount: 0 },
  { type: 'im', name: '私信', icon: ICONS['message'], colorClass: 'green', unreadCount: 12 },
]

/** 帖子动态（默认空，触发"暂无消息"） */
export const MESSAGE_FEEDS: MessageItem[] = []

/* ============ 发布 ============ */

/** 发布页热搜标签 */
export const PUBLISH_HOT_TAGS = ['考研交流', '失物招领', '二手交易', '拼车出行', '期末互助'] as const

/* ============ 我的 ============ */

export const MINE_USER: MineUser = {
  avatarUrl: ICONS['mine'],
  nickName: '鄂小鹰0001',
  schoolName: '鄂尔多斯应用技术学院',
}

export const MINE_STATS: MineStats = {
  postsCount: 124,
  commentsCount: 231,
  favoritesCount: 86,
  footprintsCount: 45,
}

export const MINE_MENU_1: MineMenu[] = [
  { name: '社区规范', icon: ICONS['shield'], action: 'guidelines' },
  { name: '新手帮助', icon: ICONS['help'], action: 'help' },
  { name: '邀请校友', icon: ICONS['invite'], action: 'invite' },
]

export const MINE_MENU_2: MineMenu[] = [
  { name: '设置', icon: ICONS['settings'], action: 'settings' },
  { name: '关于我们', icon: ICONS['about'], action: 'about' },
  { name: '联系我们', icon: ICONS['contact'], action: 'contact' },
]
