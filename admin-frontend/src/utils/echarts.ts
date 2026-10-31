/**
 * echarts 按需注册 —— 看板只用到「折线 + 类目/数值轴 + 网格 + 提示框 + 图例 + Canvas 渲染」。
 *
 * 为什么不用整包：`import('echarts')` 会拉全量 1.1MB raw / 382KB gzip，
 * 运营方每打开一次看板就整包下载一次，而整包里 20 多种图表类型一个都没用到。
 * echarts 官方提供 ESM 子路径（echarts/core、echarts/charts、echarts/components、
 * echarts/renderers），按需注册后未用到的模块会被 tree-shaking 掉。
 *
 * 新增图表类型时必须同步在这里注册，否则运行时报「组件未注册」。
 */
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  AxisPointerComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  // tooltip 的 trigger:'axis' 依赖轴指针
  AxisPointerComponent,
  CanvasRenderer,
])

export { echarts }
export type { ECharts } from 'echarts/core'
