<template>
  <view class="page-create" :class="themeClass">
    <view class="form-card">
      <!-- 类型 -->
      <view class="form-item">
        <text class="label">类型</text>
        <view class="type-toggle">
          <view class="type-opt" :class="{ on: form.type === 'group' }" @tap="form.type = 'group'"><text>组局</text></view>
          <view class="type-opt" :class="{ on: form.type === 'purchase' }" @tap="form.type = 'purchase'"><text>拼单</text></view>
        </view>
      </view>

      <!-- 分类 -->
      <view class="form-item" @tap="pickCategory">
        <text class="label">分类</text>
        <view class="picker-row">
          <text :class="form.category ? 'picker-val' : 'picker-ph'">{{ form.category || '选择分类' }}</text>
          <text class="arrow">›</text>
        </view>
      </view>

      <!-- 标题 -->
      <view class="form-item">
        <text class="label">标题</text>
        <input class="input" v-model="form.title" placeholder="一句话说明（如：今晚图书馆自习）" :maxlength="60" placeholder-class="ph" />
      </view>

      <!-- 详情 -->
      <view class="form-item">
        <text class="label">详情</text>
        <textarea class="textarea" v-model="form.content" placeholder="时间/地点/要求等详细说明" :maxlength="500" placeholder-class="ph" />
      </view>

      <!-- 人数 + 地点 -->
      <view class="form-item">
        <text class="label">名额</text>
        <input class="input num" type="number" v-model="form.total" placeholder="4" placeholder-class="ph" />
      </view>
      <view class="form-item">
        <text class="label">地点（选填）</text>
        <input class="input" v-model="form.location" placeholder="如：东校区图书馆" :maxlength="50" placeholder-class="ph" />
      </view>
    </view>

    <view class="submit-bar">
      <button class="submit-btn" :class="{ disabled: submitting }" @tap="onSubmit">发 布 组 局</button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useTheme } from '@/utils/theme'
import { createParty, type PartyType } from '@/api/party'

const { themeClass } = useTheme()

const CATS = ['自习', '电影', '聚餐', '拼车', '拼单', '运动', '游戏', '旅行', '其他']

const form = reactive({
  type: 'group' as PartyType,
  category: '',
  title: '',
  content: '',
  total: '4',
  location: '',
})
const submitting = ref(false)

const pickCategory = () => {
  uni.showActionSheet({
    itemList: CATS,
    success: (r) => { form.category = CATS[r.tapIndex] },
  })
}

const onSubmit = async () => {
  if (submitting.value) return
  if (!form.category) return uni.showToast({ title: '请选择分类', icon: 'none' })
  if (!form.title.trim()) return uni.showToast({ title: '请填写标题', icon: 'none' })
  if (!form.content.trim()) return uni.showToast({ title: '请填写详情', icon: 'none' })
  const total = parseInt(form.total, 10)
  if (!total || total < 1) return uni.showToast({ title: '名额需 ≥ 1', icon: 'none' })

  submitting.value = true
  try {
    await createParty({
      type: form.type,
      category: form.category,
      title: form.title.trim(),
      content: form.content.trim(),
      total,
      location: form.location.trim() || undefined,
    })
    uni.showToast({ title: '发布成功', icon: 'success' })
    setTimeout(() => uni.navigateBack(), 900)
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '发布失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.page-create { min-height: 100vh; background: var(--bg-page); padding: 24rpx; }
.form-card { background: var(--bg-card); border-radius: var(--radius-card); padding: 8rpx 28rpx; }
.form-item { padding: 28rpx 0; border-bottom: 1rpx solid var(--border-light); display: flex; align-items: center; }
.form-card .form-item:last-child { border-bottom: none; }
.label { width: 160rpx; font-size: 28rpx; color: var(--text-1); flex-shrink: 0; }
.input { flex: 1; font-size: 28rpx; color: var(--text-1); }
.textarea { flex: 1; font-size: 28rpx; color: var(--text-1); min-height: 120rpx; }
.num { width: 120rpx; flex: none; }

.type-toggle { display: flex; gap: 16rpx; }
.type-opt { padding: 12rpx 32rpx; border-radius: 32rpx; background: var(--bg-card-2); font-size: 26rpx; color: var(--text-2); }
.type-opt.on { background: var(--primary); color: var(--text-inverse); }

.picker-row { flex: 1; display: flex; align-items: center; justify-content: space-between; }
.picker-val { font-size: 28rpx; color: var(--text-1); }
.picker-ph { font-size: 28rpx; color: var(--text-4); }
.arrow { color: var(--text-4); font-size: 32rpx; }

.submit-bar { margin-top: 48rpx; padding: 0 16rpx; }
.submit-btn { width: 100%; height: 92rpx; background: var(--primary); color: var(--text-inverse); border-radius: var(--radius-btn); font-size: 32rpx; font-weight: bold; line-height: 92rpx; box-shadow: var(--shadow-primary-lg); }
.submit-btn.disabled { opacity: 0.5; }
</style>
