<template>
  <div>
    <!-- 统计卡 -->
    <el-row :gutter="16">
      <el-col :span="4" v-for="card in cards" :key="card.label">
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
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import type { ECharts } from 'echarts'
import { getStats, getTrends, type AdminStats, type TrendPoint } from '@/api/stats'

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
let echartsPromise: Promise<typeof import('echarts')> | null = null

const getECharts = () => {
  // 按需异步加载 echarts：登录页/其他页面不承担图表体积
  if (!echartsPromise) echartsPromise = import('echarts')
  return echartsPromise
}

const loadStats = async () => {
  try { stats.value = await getStats() } catch { /* 拦截器已提示 */ }
}

const renderChart = async () => {
  if (!chartEl.value) return
  const echarts = await getECharts()
  if (!chart) chart = echarts.init(chartEl.value)
  const dates = series.value.map(p => p.date.slice(5))
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['帖子', '评论', '点赞', '新用户', '活跃用户'] },
    grid: { left: 40, right: 20, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      { name: '帖子', type: 'line', smooth: true, data: series.value.map(p => p.posts), itemStyle: { color: '#f73b43' } },
      { name: '评论', type: 'line', smooth: true, data: series.value.map(p => p.comments), itemStyle: { color: '#409eff' } },
      { name: '点赞', type: 'line', smooth: true, data: series.value.map(p => p.likes), itemStyle: { color: '#e6a23c' } },
      { name: '新用户', type: 'line', smooth: true, data: series.value.map(p => p.new_users), itemStyle: { color: '#67c23a' } },
      { name: '活跃用户', type: 'line', smooth: true, data: series.value.map(p => p.active_users), itemStyle: { color: '#909399' } },
    ],
  })
}

const loadTrends = async () => {
  try {
    const res = await getTrends(days.value)
    series.value = res.series
    await renderChart()
  } catch { /* 拦截器已提示 */ }
}

const onResize = () => chart?.resize()

onMounted(() => {
  loadStats()
  loadTrends()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
})
</script>

<style scoped>
.stat-card { text-align: center; }
.stat-value { font-size: 28px; font-weight: bold; color: #303133; }
.stat-label { font-size: 13px; color: #909399; margin-top: 4px; }
.stat-card.warn .stat-value { color: #f73b43; }
.trend-card { margin-top: 16px; }
.trend-header { display: flex; justify-content: space-between; align-items: center; }
.chart { height: 380px; }
</style>
