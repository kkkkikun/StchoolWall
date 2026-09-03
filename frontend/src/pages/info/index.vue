<template>
  <view class="page-info">
    <view class="info-card">
      <text class="info-title">{{ content.title }}</text>
      <text v-for="(p, i) in content.paras" :key="i" class="info-para">{{ p }}</text>

      <!-- 邀请校友：一键复制邀请文案 -->
      <view v-if="infoType === 'invite'" class="invite-btn" @tap="copyInvite">
        <text>复制邀请文案</text>
      </view>
    </view>
    <text class="footer">鄂应墙 · 校园信息撮合平台</text>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'

type InfoType = 'community' | 'invite' | 'about' | 'contact'

const INFO_MAP: Record<InfoType, { title: string; paras: string[] }> = {
  community: {
    title: '社区规范',
    paras: [
      '一、发帖规范',
      '1. 禁止发布违法违规、色情低俗、赌博诈骗等内容；',
      '2. 禁止人身攻击、地域歧视与泄露他人隐私（含真实姓名、联系方式、住址等）；',
      '3. 二手交易请如实描述，线下交易当面验货；',
      '4. 拼车、组局等线下活动请注意人身与财产安全。',
      '',
      '二、互动规范',
      '1. 文明评论，理性讨论，尊重每一位同学；',
      '2. 发现违规内容请及时举报，管理团队会尽快核实处理；',
      '3. 多次违规者将被冻结账号。',
    ],
  },
  invite: {
    title: '邀请校友',
    paras: [
      '把鄂应墙分享给身边的同学，一起让校园生活更有趣！',
      '',
      '点击下方按钮复制邀请文案，粘贴发给同学即可。',
    ],
  },
  about: {
    title: '关于我们',
    paras: [
      '鄂应墙是鄂尔多斯应用技术学院的校园信息撮合平台。',
      '',
      '在这里可以发布二手交易、失物招领、组局拼车、表白墙等校园动态，也可以浏览热帖榜单、找到志同道合的伙伴。',
      '',
      '版本 v1.0.0',
    ],
  },
  contact: {
    title: '联系我们',
    paras: [
      '如有问题、建议或合作意向，欢迎联系：',
      '',
      '· 微信：eywall-admin（注明来意）',
      '· 邮箱：admin@eywall.cn',
      '',
      '处理时间：工作日 9:00 - 18:00',
    ],
  },
}

const infoType = ref<InfoType>('about')
const content = ref(INFO_MAP.about)

onLoad((opts) => {
  const t = (opts?.type || 'about') as InfoType
  if (t in INFO_MAP) {
    infoType.value = t
    content.value = INFO_MAP[t]
  }
  uni.setNavigationBarTitle({ title: content.value.title })
})

const copyInvite = () => {
  uni.setClipboardData({
    data: '我在用鄂应墙——校园二手/失物/组局/表白墙一站式信息平台，快来加入：https://eywall.cn',
    success: () => uni.showToast({ title: '已复制，快发给同学吧', icon: 'none' }),
  })
}
</script>

<style scoped>
.page-info { min-height: 100vh; background: var(--bg-page); padding: 24rpx; }
.info-card { background: #ffffff; border-radius: var(--radius-card); padding: 40rpx 32rpx; }
.info-title { display: block; font-size: 34rpx; font-weight: bold; color: var(--text-1); margin-bottom: 24rpx; }
.info-para { display: block; font-size: 26rpx; color: var(--text-2); line-height: 1.9; }
.invite-btn {
  margin-top: 36rpx;
  background: var(--brand-red-dark);
  color: #ffffff;
  font-size: 28rpx;
  text-align: center;
  padding: 20rpx 0;
  border-radius: 36rpx;
}
.footer { display: block; text-align: center; margin-top: 40rpx; font-size: 22rpx; color: var(--text-3); }
</style>
