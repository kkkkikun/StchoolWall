<template>
  <view class="container">
    <view class="tabs">
      <view
        v-for="tab in tabs"
        :key="tab.value"
        class="tab"
        :class="{ active: currentTab === tab.value }"
        @tap="switchTab(tab.value)"
      >
        {{ tab.label }}
      </view>
    </view>

    <scroll-view class="content" scroll-y>
      <view v-if="currentTab === 'reports'" class="section">
        <view v-for="report in reports" :key="report.id" class="report-card">
          <view class="report-header">
            <text class="post-id">帖子 #{{ report.post_id }}</text>
            <text class="reason">{{ report.reason }}</text>
          </view>
          <text v-if="report.description" class="description">{{ report.description }}</text>
          <view class="actions">
            <button class="btn btn-approve" @tap="handleReport(report.id, 'approve')">通过</button>
            <button class="btn btn-reject" @tap="handleReport(report.id, 'reject')">驳回</button>
          </view>
        </view>
        <view v-if="reports.length === 0" class="empty">
          <text>暂无举报</text>
        </view>
      </view>

      <view v-if="currentTab === 'users'" class="section">
        <view v-for="user in users" :key="user.id" class="user-card">
          <image class="avatar" :src="user.avatar_url || '/static/default-avatar.png'" />
          <view class="user-info">
            <text class="nickname">{{ user.nickname }}</text>
            <text class="meta">{{ user.role }} | {{ user.is_verified ? '已认证' : '未认证' }}</text>
          </view>
        </view>
        <view v-if="users.length === 0" class="empty">
          <text>暂无用户</text>
        </view>
      </view>
    </scroll-view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { UserInfo } from '@/types/api'
import { userStorage } from '@/utils/storage'
import { getReports, getUsers } from '@/api/admin'

interface Tab {
  label: string
  value: string
}

interface Report {
  id: number
  post_id: number
  reason: string
  description?: string
}

const tabs: Tab[] = [
  { label: '举报管理', value: 'reports' },
  { label: '用户管理', value: 'users' },
]

const currentTab = ref('reports')
const reports = ref<Report[]>([])
const users = ref<UserInfo[]>([])

const switchTab = (tab: string) => {
  currentTab.value = tab
}

const handleReport = async (reportId: number, action: string) => {
  uni.showToast({ title: action === 'approve' ? '已通过' : '已驳回', icon: 'success' })
  reports.value = reports.value.filter((r) => r.id !== reportId)
}

onMounted(() => {
  const userInfo = userStorage.getUserInfo()
  if (!userInfo || userInfo.role !== 'admin') {
    uni.showToast({ title: '无权访问', icon: 'none' })
    setTimeout(() => uni.navigateBack(), 1000)
    return
  }

  fetchReports()
  fetchUsers()
})

const fetchReports = async () => {
  try {
    reports.value = await getReports()
  } catch (e) {
    console.error('Failed to load reports:', e)
  }
}

const fetchUsers = async () => {
  try {
    users.value = await getUsers()
  } catch (e) {
    console.error('Failed to load users:', e)
  }
}
</script>

<style scoped>
.container {
  min-height: 100vh;
  background: #f5f5f5;
  display: flex;
  flex-direction: column;
}

.tabs {
  display: flex;
  background: #fff;
  padding: 16rpx 20rpx;
  gap: 16rpx;
}

.tab {
  flex: 1;
  text-align: center;
  padding: 12rpx 0;
  font-size: 26rpx;
  color: #666;
  border-radius: 8rpx;
}

.tab.active {
  background: #1296db;
  color: #fff;
}

.content {
  flex: 1;
  padding: 20rpx;
}

.section {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.report-card {
  background: #fff;
  padding: 24rpx;
  border-radius: 16rpx;
}

.report-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12rpx;
}

.post-id {
  font-size: 28rpx;
  font-weight: 600;
  color: #333;
}

.reason {
  font-size: 24rpx;
  color: #ff6b6b;
}

.description {
  font-size: 26rpx;
  color: #666;
  display: block;
  margin-bottom: 16rpx;
}

.actions {
  display: flex;
  gap: 12rpx;
}

.btn {
  flex: 1;
  height: 64rpx;
  line-height: 64rpx;
  text-align: center;
  border-radius: 8rpx;
  font-size: 26rpx;
  border: none;
}

.btn-approve {
  background: #e6f7ff;
  color: #1296db;
}

.btn-reject {
  background: #ffe6e6;
  color: #ff6b6b;
}

.user-card {
  background: #fff;
  padding: 24rpx;
  border-radius: 16rpx;
  display: flex;
  align-items: center;
}

.avatar {
  width: 80rpx;
  height: 80rpx;
  border-radius: 50%;
  margin-right: 16rpx;
}

.user-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.nickname {
  font-size: 28rpx;
  font-weight: 600;
  color: #333;
}

.meta {
  font-size: 24rpx;
  color: #999;
  margin-top: 4rpx;
}

.empty {
  text-align: center;
  padding: 80rpx 0;
  color: #999;
  font-size: 26rpx;
}
</style>
