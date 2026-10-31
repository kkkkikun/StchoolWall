import { getCurrentInstance, onMounted, ref, type Ref } from 'vue'

export interface ScrollFade {
  /** 左侧还有内容可向左滚动时才显示（左渐隐） */
  showLeft: Ref<boolean>
  /** 右侧还有内容可向右滚动时才显示（右渐隐） */
  showRight: Ref<boolean>
  /** 绑定到 <scroll-view @scroll="onScroll"> */
  onScroll: (e: unknown) => void
}

/**
 * 横向滚动行两侧渐隐。
 *
 * 背景：横向滚动的分类/筛选行在容器边缘会把胶囊从字形中间硬切，看起来像渲染坏了。
 * 小程序不支持 CSS mask，故用覆盖层实现：绝对定位的渐变层盖住切边，视觉上自然淡出。
 *
 * 依赖：滚动容器自身不加左右内边距（内边距放在滚动内容上），
 * 这样容器可视宽度 == 测量宽度，滚动位移换算才准确。
 */
export function useScrollFade(selector: string): ScrollFade {
  const showLeft = ref(false)
  const showRight = ref(true)
  let clientWidth = 0

  const measure = () => {
    const inst = getCurrentInstance()
    const query = uni.createSelectorQuery()
    if (inst?.proxy) query.in(inst.proxy as never)
    query
      .select(selector)
      .boundingClientRect((rect: unknown) => {
        const r = rect as { width?: number } | null
        if (r?.width) clientWidth = r.width
      })
      .exec()
  }

  const onScroll = (e: unknown) => {
    const detail = (e as { detail?: Record<string, number> })?.detail || {}
    const scrollLeft = detail.scrollLeft || 0
    const scrollWidth = detail.scrollWidth || 0
    // 测量失败时 clientWidth 为 0，退化为「右侧常显」，仍是可接受的降级
    const maxScroll = Math.max(0, scrollWidth - clientWidth)
    showLeft.value = scrollLeft > 2
    showRight.value = scrollLeft < maxScroll - 2
  }

  onMounted(() => {
    measure()
    // 布局稳定后再量一次，覆盖字体/异步数据导致的宽度变化
    setTimeout(measure, 300)
  })

  return { showLeft, showRight, onScroll }
}
