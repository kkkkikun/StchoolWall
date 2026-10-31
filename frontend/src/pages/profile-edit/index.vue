<template>
  <view class="page-edit" :class="themeClass">
    <!-- 横幅预览（点击更换） -->
    <view class="banner-prev" @tap="changeImage('banners')">
      <image v-if="form.banner_url" class="banner-img" :src="form.banner_url" mode="aspectFill" />
      <view v-else class="banner-ph">
        <image class="ph-icon" src="/static/icons/common/camera.svg" mode="aspectFit" />
        <text>点击设置主页横幅</text>
      </view>
    </view>

    <!-- 头像（点击更换） -->
    <view class="avatar-row">
      <view class="avatar-ring" @tap="changeImage('avatars')">
        <image v-if="form.avatar_url" class="avatar-img" :src="form.avatar_url" mode="aspectFill" />
        <view v-else class="avatar-ph">
          <image class="ph-icon" src="/static/icons/common/camera.svg" mode="aspectFit" />
        </view>
        <view class="avatar-cam">
          <image class="cam-icon" src="/static/icons/common/camera-inverse.svg" mode="aspectFit" />
        </view>
      </view>
      <text class="avatar-tip">点击图片可更换</text>
    </view>

    <!-- 表单 -->
    <view class="form-card">
      <view class="field">
        <text class="label">昵称</text>
        <input v-model="form.nickname" class="input" :maxlength="50" placeholder="给自己起个名字" placeholder-class="ph" />
      </view>
      <view class="field">
        <text class="label">简介</text>
        <textarea
          v-model="form.bio"
          class="textarea"
          :maxlength="200"
          placeholder="介绍一下自己吧（选填）"
          placeholder-class="ph"
          auto-height
        />
        <text class="counter">{{ (form.bio || '').length }}/200</text>
      </view>
      <view class="field">
        <text class="label">微信号</text>
        <input v-model="form.wechat_id" class="input" :maxlength="50" placeholder="方便同学联系你（选填）" placeholder-class="ph" />
      </view>
    </view>

    <!-- 认证信息（只读） -->
    <view class="form-card">
      <view class="field">
        <text class="label">真实姓名</text>
        <text class="readonly">为保护隐私不保留姓名</text>
      </view>
      <view class="field">
        <text class="label">学号</text>
        <text class="readonly">仅保留不可逆身份指纹</text>
      </view>
      <text class="ro-tip">学生证经人工核验，认证状态以服务器为准；如需申诉请联系支持</text>
    </view>

    <!-- 保存 -->
    <view class="save-btn" :class="{ saving }" @tap="onSave">
      <text>{{ saving ? '保存中…' : '保存' }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useTheme } from '@/utils/theme'
import { onShow } from '@dcloudio/uni-app'
import { get, put, uploadMedia } from '@/utils/request'
import { tokenStorage, userStorage } from '@/utils/storage'

const { themeClass } = useTheme()

interface ProfileForm {
  nickname: string
  bio: string
  wechat_id: string
  avatar_url: string
  banner_url: string
  real_name: string | null
  student_id: string | null
}

const form = ref<ProfileForm>({
  nickname: '',
  bio: '',
  wechat_id: '',
  avatar_url: '',
  banner_url: '',
  real_name: null,
  student_id: null,
})
const saving = ref(false)

const load = async () => {
  try {
    const p = await get<ProfileForm>('/user/profile')
    form.value = {
      nickname: p.nickname || '',
      bio: p.bio || '',
      wechat_id: p.wechat_id || '',
      avatar_url: p.avatar_url || '',
      banner_url: p.banner_url || '',
      real_name: p.real_name,
      student_id: p.student_id,
    }
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '加载失败', icon: 'none' })
  }
}

onShow(() => {
  if (!tokenStorage.isLoggedIn()) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    setTimeout(() => uni.navigateBack(), 800)
    return
  }
  load()
})

/** 头像/横幅：选图 → 上传 → 即时持久化（与我的页同一链路） */
const changeImage = (kind: 'avatars' | 'banners') => {
  uni.chooseImage({
    count: 1,
    sizeType: ['compressed'],
    success: async (res) => {
      const filePath = res.tempFilePaths[0]
      if (!filePath) return
      uni.showLoading({ title: '上传中…' })
      try {
        const media = await uploadMedia(filePath, kind)
        const field = kind === 'avatars' ? 'avatar_media_id' : 'banner_media_id'
        await put('/user/profile', { [field]: media.media_id })
        uni.hideLoading()
        uni.showToast({ title: '图片已提交审核', icon: 'none' })
      } catch (e) {
        uni.hideLoading()
        uni.showToast({ title: (e as Error).message || '更换失败', icon: 'none' })
      }
    },
  })
}

const onSave = async () => {
  const nickname = form.value.nickname.trim()
  if (!nickname) {
    uni.showToast({ title: '昵称不能为空', icon: 'none' })
    return
  }
  saving.value = true
  try {
    await put('/user/profile', {
      nickname,
      bio: form.value.bio.trim(),
      wechat_id: form.value.wechat_id.trim(),
    })
    // 同步本地缓存的昵称（顶栏/首页等处直接读缓存）
    const info = userStorage.getUserInfo()
    if (info) userStorage.setUserInfo({ ...info, nickname })
    uni.showToast({ title: '已保存', icon: 'success' })
    setTimeout(() => uni.navigateBack(), 600)
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '保存失败', icon: 'none' })
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.page-edit { min-height: 100vh; background: var(--bg-page); padding-bottom: 60rpx; }

.banner-prev { height: 280rpx; background: var(--hero-gradient); }
.banner-img { width: 100%; height: 100%; }
.banner-ph {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
  font-size: 26rpx;
  color: var(--text-inverse);
  opacity: 0.9;
}

.avatar-row { display: flex; align-items: center; gap: 20rpx; padding: 24rpx 40rpx 0; }
.avatar-ring {
  position: relative;
  padding: 6rpx;
  background: var(--bg-card);
  border-radius: 50%;
  box-shadow: var(--shadow-float);
  margin-top: -50rpx;
}
.avatar-img, .avatar-ph { width: 140rpx; height: 140rpx; border-radius: 50%; }
.avatar-ph {
  background: var(--primary-soft);
  display: flex;
  align-items: center;
  justify-content: center;
}
.ph-icon { width: 48rpx; height: 48rpx; flex-shrink: 0; }
.banner-ph .ph-icon { width: 32rpx; height: 32rpx; }
.cam-icon { width: 26rpx; height: 26rpx; }
.avatar-cam {
  position: absolute;
  right: -2rpx;
  bottom: -2rpx;
  width: 48rpx;
  height: 48rpx;
  border-radius: 50%;
  background: var(--primary-strong);
  border: 4rpx solid #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22rpx;
}
.avatar-tip { font-size: 22rpx; color: var(--text-3); margin-top: 40rpx; }

.form-card {
  background: var(--bg-card);
  border-radius: var(--radius-card);
  margin: 24rpx 24rpx 0;
  padding: 8rpx 32rpx;
}
.field { padding: 26rpx 0; border-bottom: 1rpx solid var(--border-light); position: relative; }
.field:last-child { border-bottom: none; }
.label { display: block; font-size: 24rpx; color: var(--text-3); margin-bottom: 12rpx; }
.input { font-size: 28rpx; color: var(--text-1); }
.textarea { font-size: 28rpx; color: var(--text-1); width: 100%; min-height: 100rpx; line-height: 1.6; }
.ph { color: var(--text-placeholder); }
.counter { position: absolute; right: 0; bottom: 26rpx; font-size: 22rpx; color: var(--text-3); }
.readonly { font-size: 28rpx; color: var(--text-2); }
.ro-tip { display: block; font-size: 22rpx; color: var(--text-3); padding: 16rpx 0 8rpx; line-height: 1.6; }

.save-btn {
  margin: 40rpx 24rpx 0;
  background: var(--primary-badge);
  color: var(--text-inverse);
  font-size: 30rpx;
  font-weight: 600;
  text-align: center;
  padding: 24rpx 0;
  border-radius: 40rpx;
}
.save-btn.saving { opacity: 0.6; }
</style>
