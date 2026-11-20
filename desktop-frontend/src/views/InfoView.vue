<script setup lang="ts">
/**
 * 信息页：社区规范 / 隐私政策 / 用户协议 / 关于我们 / 联系我们。
 *
 * 用路由参数区分内容（/info/:type），内容按校园墙场景撰写，
 * 与学生端信息页保持同一口径。
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'

const route = useRoute()

export type InfoType = 'community' | 'privacy' | 'agreement' | 'about' | 'contact' | 'invite'

interface InfoContent {
  title: string
  sections: { heading: string; paragraphs: string[] }[]
  /** 邀请页额外提供一键复制的邀请文案。 */
  inviteText?: string
}

const INFO_MAP: Record<InfoType, InfoContent> = {
  community: {
    title: '社区规范',
    sections: [
      {
        heading: '一、发帖规范',
        paragraphs: [
          '禁止发布违法违规、色情低俗、赌博诈骗等内容。',
          '禁止人身攻击、地域歧视与泄露他人隐私（含真实姓名、联系方式、住址等）。',
          '二手交易请如实描述，线下交易当面验货。',
          '拼车、组局等线下活动请注意人身与财产安全。',
          '禁止发布与本校无关的广告、引流与刷屏内容。',
        ],
      },
      {
        heading: '二、互动规范',
        paragraphs: [
          '文明评论，理性讨论，尊重每一位同学。',
          '发现违规内容请及时举报，管理团队会尽快核实处理。',
          '禁止在评论区发布联系方式进行私下交易引流。',
          '多次违规者将被冻结账号。',
        ],
      },
      {
        heading: '三、认证与处置',
        paragraphs: [
          '学生证认证通过后账号获得「已认证」标识，认证结果最长有效 12 个月。',
          '被认证驳回、撤销或过期的同学可在认证页发起申诉，管理团队会复核后给出处理说明。',
          '账号被冻结或内容被下架时，处置原因会通过站内通知告知。',
        ],
      },
    ],
  },
  privacy: {
    title: '隐私政策',
    sections: [
      {
        heading: '一、我们收集哪些信息',
        paragraphs: [
          '我们非常重视你的个人信息安全。本应用仅收集提供服务所必需的信息。',
          '登录注册：保存密码的单向哈希，不保存明文密码。浏览器刷新会话使用 HttpOnly Cookie；手机端刷新凭据由设备安全存储加密保护。可在设置中查看和撤销登录会话。',
          '学生证认证：不再收集教务密码。经你主动同意后，使用学生证和同框手写拍摄码人工核验；仅保存学校、学号的不可逆身份指纹和审核状态，不保存明文学号或姓名。',
        ],
      },
      {
        heading: '二、证件照片如何处理',
        paragraphs: [
          '私有照片只供授权管理员查看，不公开，不送交外部内容审核。',
          '审核结束 7 天后删除，待审超过 14 天自动过期并删除。',
          '认证最长有效 12 个月，或更早的证件有效期。',
        ],
      },
      {
        heading: '三、发布内容与联系方式',
        paragraphs: [
          '帖子、评论、头像等在通过审核后公开。普通内容和图片可能发送至腾讯云内容安全服务进行审核；学生证照片不进入此流程。请勿在公开内容中披露他人信息。',
          '帖子详情仅在交易 / 拼车等必要场景向认证用户展示微信号，游客不可见。',
        ],
      },
      {
        heading: '四、权限与你的控制',
        paragraphs: [
          '仅在你主动拍照、认证或选择图片时请求必要权限，拒绝后可以继续浏览；不申请通讯录、电话状态、账号列表、系统日志或位置权限。可在系统设置中撤回授权。',
          '你可以在设置中注销账号、撤销设备会话，或在屏蔽列表中解除对特定用户的屏蔽。',
        ],
      },
      {
        heading: '五、联系我们',
        paragraphs: [
          '法定保留记录与反滥用身份指纹的保存范围、具体期限及申诉删除方式，可通过「联系我们」页面反馈，我们会在核实后答复。',
        ],
      },
    ],
  },
  agreement: {
    title: '用户协议',
    sections: [
      {
        heading: '一、协议的接受',
        paragraphs: [
          '欢迎使用鄂应墙。使用本服务即表示你已阅读并同意本协议。',
          '若你未满十八周岁，请在监护人陪同下阅读本协议并在其同意后使用。',
        ],
      },
      {
        heading: '二、你的使用义务',
        paragraphs: [
          '请遵守国家法律法规，不发布违法违规、色情低俗、赌博诈骗等信息。',
          '不进行人身攻击、地域歧视或泄露他人隐私。',
          '不冒用他人身份、不伪造证件，不对认证流程进行绕过。',
          '二手交易、拼车、组局等线下行为请自行甄别风险，注意人身与财产安全。',
        ],
      },
      {
        heading: '三、账号与内容归属',
        paragraphs: [
          '你对自己账号下发布的内容负责，并对内容承担相应法律责任。',
          '你发布的帖子、评论等内容的著作权归你所有；鄂应墙享有为提供服务所必需的展示、推广与存储权利。',
          '管理团队有权对违规内容进行删除、对违规账号进行冻结或封禁。',
        ],
      },
      {
        heading: '四、服务的变更与终止',
        paragraphs: [
          '鄂应墙可能因运营需要调整、暂停或终止部分服务，并在站内公告中说明。',
          '你可以在设置中随时注销账号；注销后历史内容将显示为「已注销用户」。',
        ],
      },
      {
        heading: '五、反馈与争议',
        paragraphs: [
          '如发现违规内容，请通过举报或「联系我们」反馈；如对处理结果有异议，可在「申诉与处理记录」中发起申诉。',
        ],
      },
    ],
  },
  about: {
    title: '关于我们',
    sections: [
      {
        heading: '鄂应墙是什么',
        paragraphs: [
          '鄂应墙是鄂尔多斯应用技术学院的校园信息撮合平台。',
          '在这里可以发布二手交易、失物招领、组局拼车、表白墙等校园动态，也可以浏览热帖榜单、找到志同道合的伙伴。',
        ],
      },
      {
        heading: '我们想解决什么问题',
        paragraphs: [
          '校园里的信息长期散落在群聊与二手平台里：失物招领找不到失主、闲置物品流转成本高、组局拼车缺少可信的同校圈子。',
          '鄂应墙用学生证认证把「同校」这件事坐实，再把交易、失物、组局、闲聊这些高频场景聚到一处，让校园信息在合适的圈层里流动。',
        ],
      },
      {
        heading: '隐私与安全',
        paragraphs: [
          '我们只收集提供服务所必需的信息；学号以不可逆指纹保存，明文不落库。',
          '证件照片仅供授权管理员人工核验，不公开、不送交外部内容审核服务。',
        ],
      },
      {
        heading: '版本',
        paragraphs: ['电脑版 v1.0.0 · 鄂应墙 · 校园信息撮合平台'],
      },
    ],
  },
  contact: {
    title: '联系我们',
    sections: [
      {
        heading: '反馈与建议',
        paragraphs: [
          '如有问题、建议或合作意向，欢迎联系：',
          '· 微信：eywall-admin（注明来意）',
          '· 邮箱：admin@eywall.cn',
        ],
      },
      {
        heading: '处理时间',
        paragraphs: ['工作日 9:00 - 18:00，一般问题当天回复；申诉与账号问题需要人工复核，可能需要 1-3 个工作日。'],
      },
      {
        heading: '更快的反馈入口',
        paragraphs: [
          '电脑版内点击右上角的意见反馈按钮（快捷键 Ctrl + Shift + F），可以直接附上截图与当场的诊断信息，便于我们定位问题。',
          '违规内容请使用帖子内的举报入口举报，比私信反馈处理更快。',
        ],
      },
    ],
  },
  invite: {
    title: '邀请校友',
    inviteText:
      '我在用鄂应墙——校园二手 / 失物 / 组局 / 表白墙一站式信息平台，快来加入：https://eywall.cn',
    sections: [
      {
        heading: '邀请同学加入',
        paragraphs: [
          '把鄂应墙分享给身边的同学，一起让校园生活更有趣。',
          '复制下面的邀请文案，粘贴到微信群、朋友圈或班级群即可。',
        ],
      },
      {
        heading: '关于邀请码',
        paragraphs: [
          '当前版本尚未开放邀请码与邀请奖励功能，本页仅提供官方邀请文案，不会记录你的邀请关系。',
          '待邀请码功能上线后，这里会显示你的专属邀请码与邀请进度，届时会另行公告。',
        ],
      },
    ],
  },
}

const infoType = computed<InfoType>(() => {
  const raw = String(route.params.type ?? '')
  return (raw in INFO_MAP ? raw : 'about') as InfoType
})

const content = computed(() => INFO_MAP[infoType.value])

/** 复制邀请文案。剪贴板不可用时提示手动复制，不静默失败。 */
async function copyInvite(): Promise<void> {
  const text = content.value.inviteText
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制，快发给同学吧')
  } catch {
    ElMessage.warning('浏览器不允许自动复制，请手动选中下方文案复制')
  }
}
</script>

<template>
  <article class="sw-info">
    <div class="sw-card sw-info__card">
      <h3 class="sw-card__title">{{ content.title }}</h3>
      <section v-for="section in content.sections" :key="section.heading" class="sw-info__section">
        <h4 class="sw-info__heading">{{ section.heading }}</h4>
        <p v-for="(paragraph, index) in section.paragraphs" :key="index" class="sw-info__paragraph">
          {{ paragraph }}
        </p>
      </section>

      <template v-if="content.inviteText">
        <p class="sw-info__invite-text">{{ content.inviteText }}</p>
        <el-button type="primary" class="sw-info__invite-btn" @click="copyInvite">
          复制邀请文案
        </el-button>
      </template>
    </div>
    <p class="sw-info__footer">鄂应墙 · 校园信息撮合平台</p>
  </article>
</template>

<style scoped>
.sw-info {
  display: flex;
  flex-direction: column;
  gap: var(--sw-space-4);
}

.sw-info__card {
  padding: var(--sw-space-5);
}

.sw-info__section {
  margin-top: var(--sw-space-4);
}

.sw-info__heading {
  margin: 0 0 var(--sw-space-2);
  font-size: var(--sw-text-base);
  font-weight: 600;
  color: var(--sw-text);
}

.sw-info__paragraph {
  margin: 0 0 var(--sw-space-1);
  color: var(--sw-text-secondary);
  font-size: var(--sw-text-sm);
  line-height: 1.9;
}

.sw-info__footer {
  margin: 0;
  text-align: center;
  color: var(--sw-text-muted);
  font-size: var(--sw-text-xs);
}

.sw-info__invite-text {
  margin: var(--sw-space-4) 0 0;
  padding: var(--sw-space-3);
  background: var(--sw-surface-muted);
  border-radius: var(--sw-radius-sm);
  color: var(--sw-text-secondary);
  font-size: var(--sw-text-sm);
  line-height: 1.8;
}

.sw-info__invite-btn {
  margin-top: var(--sw-space-3);
}
</style>
