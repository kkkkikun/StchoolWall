<template>
  <div class="dashboard-page">
    <!-- 统计卡 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :xs="12" :sm="8" :lg="4" v-for="card in cards" :key="card.label" class="stat-col">
        <el-card shadow="hover" class="stat-card" :class="{ warn: card.warn && Number(card.value) > 0 }">
          <div class="stat-value">{{ card.value }}</div>
          <div class="stat-label">{{ card.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 趋势图 -->
    <el-card shadow="never" class="trend-card">
      <template #header>
        <div class="trend-header">
          <span>内容趋势</span>
          <el-radio-group v-model="days" size="small" @change="loadTrends">
            <el-radio-button :value="7">7 天</el-radio-button>
            <el-radio-button :value="14">14 天</el-radio-button>
            <el-radio-button :value="30">30 天</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      <div ref="chartEl" class="chart" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { ECharts } from '@/utils/echarts'
import { getStats, getTrends, type AdminStats, type TrendPoint } from '@/api/stats'
import { CHART_COLORS, CHART_TEXT, CHART_AXIS, CHART_SPLIT } from '@/theme'
import { useThemeStore } from '@/stores/theme'

const { isDark } = useThemeStore()

const stats = ref<AdminStats | null>(null)
const series = ref<TrendPoint[]>([])
const days = ref(14)

const cards = computed(() => {
  const s = stats.value
  return [
    { label: '待审帖子', value: s?.pending_posts ?? '-', warn: true },
    { label: '待处理举报', value: s?.pending_reports ?? '-', warn: true },
    { label: '今日新帖', value: s?.posts_today ?? '-' },
    { label: '总帖子', value: s?.total_posts ?? '-' },
    { label: '总用户', value: s?.total_users ?? '-' },
    { label: '冻结用户', value: s?.frozen_users ?? '-' },
  ]
})

const chartEl = ref<HTMLDivElement>()
let chart: ECharts | null = null
let echartsPromise: Promise<typeof import('@/utils/echarts')> | null = null
let resizeObserver: ResizeObserver | null = null

const getECharts = () => {
  // 按需异步加载 echarts：登录页/其他页面不承担图表体积
  if (!echartsPromise) echartsPromise = import('@/utils/echarts')
  return echartsPromise
}

const loadStats = async () => {
  try { stats.value = await getStats() } catch { /* 拦截器已提示 */ }
}

const renderChart = async () => {
  if (!chartEl.value) return
  const { echarts } = await getECharts()
  if (!chart) chart = echarts.init(chartEl.value)
  ;(window as any).__chart = chart

  const dates = (series.value || []).map(p => (p.date ? p.date.slice(5) : ''))
  const textColor = isDark.value ? CHART_TEXT : '#536471'
  const axisColor = isDark.value ? CHART_AXIS : '#cfd9de'
  const splitColor = isDark.value ? CHART_SPLIT : '#eff3f4'

  const containerW = chartEl.value.offsetWidth || 1000
  const isMobile = containerW <= 500

  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: {
      data: ['帖子', '评论', '点赞', '新用户', '活跃用户'],
      textStyle: { color: textColor, fontSize: isMobile ? 11 : 12 },
      show: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 8,
      width: isMobile ? Math.max(containerW - 24, 280) : undefined,
      itemGap: isMobile ? 10 : 18,
      itemWidth: isMobile ? 14 : 16,
      itemHeight: 8,
    },
    grid: {
      left: isMobile ? 36 : 45,
      right: isMobile ? 12 : 20,
      top: 25,
      bottom: isMobile ? 72 : 62,
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: {
        color: textColor,
        fontSize: isMobile ? 11 : 12,
        margin: 8,
        interval: 'auto',
      },
      axisLine: { lineStyle: { color: axisColor } },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: textColor },
      splitLine: { lineStyle: { color: splitColor } },
    },
    series: [
      { name: '帖子', type: 'line', smooth: true, data: (series.value || []).map(p => p.posts ?? 0), itemStyle: { color: CHART_COLORS[0] } },
      { name: '评论', type: 'line', smooth: true, data: (series.value || []).map(p => p.comments ?? 0), itemStyle: { color: CHART_COLORS[1] } },
      { name: '点赞', type: 'line', smooth: true, data: (series.value || []).map(p => p.likes ?? 0), itemStyle: { color: CHART_COLORS[2] } },
      { name: '新用户', type: 'line', smooth: true, data: (series.value || []).map(p => p.new_users ?? 0), itemStyle: { color: CHART_COLORS[3] } },
      { name: '活跃用户', type: 'line', smooth: true, data: (series.value || []).map(p => p.active_users ?? 0), itemStyle: { color: CHART_COLORS[4] } },
    ],
  }, true)
}

const loadTrends = async () => {
  try {
    const res = await getTrends(days.value)
    series.value = res?.series || []
    await renderChart()
  } catch { /* 拦截器已提示 */ }
}

const onResize = () => {
  chart?.resize()
  if (chartEl.value) {
    renderChart()
  }
}

watch(isDark, () => {
  renderChart()
})

onMounted(() => {
  loadStats()
  loadTrends()
  window.addEventListener('resize', onResize)
  if (chartEl.value && typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(() => {
      chart?.resize()
      renderChart()
    })
    resizeObserver.observe(chartEl.value)
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  resizeObserver?.disconnect()
  chart?.dispose()
})
</script>

<style scoped>
.dashboard-page {
  width: 100%;
}
.stat-col {
  margin-bottom: 16px;
}
.stat-card {
  text-align: center;
}
.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: var(--el-text-color-primary);
  line-height: 1.2;
}
.stat-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-top: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.stat-card.warn .stat-value {
  color: var(--el-color-danger);
}
.trend-card {
  margin-top: 0;
}
.trend-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.chart {
  height: 380px;
  width: 100%;
}
</style>
