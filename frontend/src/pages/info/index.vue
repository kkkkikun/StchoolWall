<template>
  <view class="page-info" :class="themeClass">
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
import { useTheme } from '@/utils/theme'
import { onLoad } from '@dcloudio/uni-app'

const { themeClass } = useTheme()

type InfoType = 'community' | 'invite' | 'about' | 'contact' | 'privacy' | 'agreement'

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
  privacy: {
    title: '隐私政策',
    paras: [
      '我们非常重视你的个人信息安全。本应用仅收集提供服务所必需的信息。',
      '',
      '1. 登录注册：保存密码的单向哈希，不保存明文密码。浏览器刷新会话使用 HttpOnly Cookie；Android 刷新凭据由设备安全存储加密保护。可在设置中查看和撤销登录会话。',
      '2. 学生证认证：不再收集教务密码。经你主动同意后，使用学生证和同框手写拍摄码人工核验；仅保存学校、学号的不可逆身份指纹和审核状态，不保存明文学号或姓名。私有照片只供授权管理员查看，不公开，不送交外部内容审核；审核结束 7 天后删除，待审超过 14 天自动过期并删除。认证最长有效 12 个月，或更早的证件有效期。',
      '3. 发布内容：帖子、评论、头像等在通过审核后公开。普通内容和图片可能发送至腾讯云内容安全服务进行审核；学生证照片不进入此流程。请勿在公开内容中披露他人信息。',
      '4. 联系方式：帖子详情仅在交易/拼车等必要场景向认证用户展示微信号，游客不可见。',
      '5. 权限：仅在你主动拍照、认证或选择图片时请求必要权限，拒绝后可以继续浏览；不申请通讯录、电话状态、账号列表、系统日志或位置权限。可在系统设置中撤回授权。',
      '6. 注销与联系：可以在设置中注销账号或撤销设备会话。法定保留记录与反滥用身份指纹的保存范围、具体期限及申诉删除方式，应由实际运营主体在正式上线政策中公布。',
      '当前为发布前政策模板：运营主体、有效联系方式、第三方 SDK 清单、备案信息和具体保留期限尚须上线前核实补齐；不能直接作为正式上架材料。',
    ],
  },
  agreement: {
    title: '用户协议',
    paras: [
      '欢迎使用鄂应墙。使用本服务即表示你已阅读并同意本协议。',
      '',
      '1. 请遵守国家法律法规，不发布违法违规、色情低俗、赌博诈骗等信息。',
      '2. 不进行人身攻击、地域歧视或泄露他人隐私。',
      '3. 二手交易、拼车、组局等线下行为请自行甄别风险，注意人身与财产安全。',
      '4. 管理团队有权对违规内容进行删除、对违规账号进行冻结或封禁。',
      '5. 如发现违规内容，请通过举报或「联系我们」反馈。',
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
.info-card { background: var(--bg-card); border-radius: var(--radius-card); padding: 40rpx 32rpx; }
.info-title { display: block; font-size: 34rpx; font-weight: bold; color: var(--text-1); margin-bottom: 24rpx; }
.info-para { display: block; font-size: 26rpx; color: var(--text-2); line-height: 1.9; }
.invite-btn {
  margin-top: 36rpx;
  background: var(--primary-strong);
  color: var(--text-inverse);
  font-size: 28rpx;
  text-align: center;
  padding: 20rpx 0;
  border-radius: 36rpx;
}
.footer { display: block; text-align: center; margin-top: 40rpx; font-size: 22rpx; color: var(--text-3); }
</style>
