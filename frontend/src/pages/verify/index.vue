<template>
  <view class="container">
    <view class="header">
      <text class="title">学籍认证</text>
      <text class="subtitle">通过正方教务系统验证您的学生身份</text>
    </view>

    <view class="form">
      <view class="form-item">
        <text class="label">学号 *</text>
        <input
          v-model="formData.student_id"
          class="input"
          placeholder="请输入学号"
          type="idcard"
        />
      </view>

      <view class="form-item">
        <text class="label">教务系统密码 *</text>
        <input
          v-model="formData.password"
          class="input"
          placeholder="请输入教务系统密码"
          type="password"
        />
      </view>

      <view class="tips">
        <text class="tips-title">认证说明：</text>
        <text class="tips-text">• 认证成功后将升级为正式学生身份</text>
        <text class="tips-text">• 您的密码仅用于验证，不会被存储</text>
        <text class="tips-text">• 认证后可发布二手交易、寻物启事等帖子</text>
      </view>
    </view>

    <view class="footer">
      <button class="submit-btn" :disabled="submitting" @tap="submit">
        {{ submitting ? '认证中...' : '开始认证' }}
      </button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { verifyStudent } from '@/api/auth'
import { userStorage, tokenStorage } from '@/utils/storage'

const formData = ref({
  student_id: '',
  password: '',
})

const submitting = ref(false)

const validate = (): boolean => {
  if (!formData.value.student_id.trim()) {
    uni.showToast({ title: '请输入学号', icon: 'none' })
    return false
  }
  if (!formData.value.password.trim()) {
    uni.showToast({ title: '请输入密码', icon: 'none' })
    return false
  }
  return true
}

const submit = async () => {
  if (!validate()) return

  submitting.value = true
  try {
    const res = await verifyStudent(formData.value.student_id, formData.value.password)
    userStorage.setUserInfo(res.user_info)
    uni.showToast({ title: '认证成功', icon: 'success' })
    setTimeout(() => uni.navigateBack(), 1500)
  } catch (e) {
    uni.showToast({ title: (e as Error).message || '认证失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.container {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 120rpx;
}

.header {
  background: linear-gradient(135deg, #1296db 0%, #0066cc 100%);
  padding: 60rpx 32rpx 80rpx;
  color: #fff;
}

.title {
  font-size: 48rpx;
  font-weight: 600;
  display: block;
  margin-bottom: 16rpx;
}

.subtitle {
  font-size: 26rpx;
  opacity: 0.9;
}

.form {
  background: #fff;
  margin: -40rpx 20rpx 0;
  padding: 32rpx 24rpx;
  border-radius: 16rpx;
}

.form-item {
  margin-bottom: 32rpx;
}

.label {
  font-size: 26rpx;
  color: #666;
  display: block;
  margin-bottom: 16rpx;
}

.input {
  width: 100%;
  padding: 24rpx;
  background: #f5f5f5;
  border-radius: 12rpx;
  font-size: 30rpx;
}

.tips {
  margin-top: 32rpx;
  padding: 20rpx;
  background: #fff9e6;
  border-radius: 12rpx;
}

.tips-title {
  font-size: 26rpx;
  font-weight: 600;
  color: #ff9800;
  display: block;
  margin-bottom: 12rpx;
}

.tips-text {
  font-size: 24rpx;
  color: #999;
  display: block;
  line-height: 1.8;
}

.footer {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 24rpx;
  background: #fff;
  border-top: 1rpx solid #eee;
}

.submit-btn {
  width: 100%;
  height: 88rpx;
  background: #1296db;
  color: #fff;
  border-radius: 12rpx;
  font-size: 32rpx;
  border: none;
}

.submit-btn[disabled] {
  background: #ccc;
}
</style>
