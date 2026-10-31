/**
 * 管理台图表配色（与 styles/theme.css 主色联动，换品牌同步改这里）
 * 顺序对应看板趋势图：帖子 / 评论 / 点赞 / 新用户 / 活跃用户
 * 色值约束：每条线在白底与暗底（#1c191c）上均 ≥3:1，图表图形达 WCAG 非文本对比。
 */
export const CHART_COLORS = ['#c2455c', '#0f7a8a', '#b5378a', '#a86400', '#7d58d8']

/** 图表文字（图例/坐标轴刻度）与轴线/网格线颜色 */
export const CHART_TEXT = '#8b8589'
export const CHART_AXIS = '#3a3437'
export const CHART_SPLIT = '#242124'
