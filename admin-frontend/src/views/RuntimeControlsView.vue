<template>
  <div class="controls-page" v-loading="loading">
    <section class="control-hero">
      <div>
        <div class="eyebrow">BETA OPERATIONS</div>
        <h1>内测设置</h1>
        <p>调整立即生效并写入操作日志，不影响已发布内容的浏览。</p>
      </div>
      <div class="live-status"><span class="live-dot" />配置实时生效</div>
    </section>

    <el-alert
      v-if="!controls.moderation_enabled"
      title="内容审核已关闭"
      description="新帖子、评论和组局将直接公开；启用中的硬违规词仍会拦截。已有待审内容不会自动通过。"
      type="warning"
      show-icon
      :closable="false"
      class="risk-alert"
    />

    <div class="control-sections">
      <section v-for="group in groups" :key="group.title" class="control-section">
        <header class="section-head">
          <div>
            <span class="section-index">{{ group.index }}</span>
            <h2>{{ group.title }}</h2>
          </div>
          <span class="section-caption">{{ group.caption }}</span>
        </header>

        <div
          v-for="item in group.items"
          :key="item.key"
          class="control-row"
          :class="{ 'is-off': !controls[item.key] }"
        >
          <div class="control-copy">
            <div class="control-title-line">
              <h3>{{ item.title }}</h3>
              <span class="state-label" :class="{ on: controls[item.key] }">
                {{ controls[item.key] ? item.onLabel : item.offLabel }}
              </span>
            </div>
            <p>{{ item.description }}</p>
            <span v-if="item.note" class="control-note">{{ item.note }}</span>
          </div>
          <el-switch
            :model-value="controls[item.key]"
            :loading="savingKey === item.key"
            :disabled="loading || (savingKey !== null && savingKey !== item.key)"
            inline-prompt
            active-text="开"
            inactive-text="关"
            :aria-label="item.title"
            @change="onSwitch(item, $event)"
          />
        </div>
      </section>
    </div>

    <section class="shortcut-section">
      <span class="shortcut-title">需要逐项管理？</span>
      <div class="shortcut-links">
        <router-link to="/sensitive-words">管理敏感词库 <span>→</span></router-link>
        <router-link to="/users">调整用户角色与状态 <span>→</span></router-link>
        <router-link to="/admins">管理后台账号 <span>→</span></router-link>
        <router-link to="/logs">查看变更日志 <span>→</span></router-link>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  getRuntimeControls,
  updateRuntimeControls,
  type RuntimeControlKey,
  type RuntimeControls,
} from '@/api/runtimeControls'

interface ControlItem {
  key: RuntimeControlKey
  title: string
  description: string
  note?: string
  onLabel: string
  offLabel: string
}

interface ControlGroup {
  index: string
  title: string
  caption: string
  items: ControlItem[]
}

const controls = reactive<RuntimeControls>({
  publishing_enabled: true,
  moderation_enabled: true,
  sensitive_words_enabled: true,
  registration_enabled: true,
  guest_posting_enabled: false,
  guest_interaction_enabled: false,
})
const loading = ref(true)
const savingKey = ref<RuntimeControlKey | null>(null)

const groups: ControlGroup[] = [
  {
    index: '01', title: '内容与审核', caption: '控制新内容的提交和公开方式',
    items: [
      {
        key: 'publishing_enabled', title: '内容发布', onLabel: '开放', offLabel: '暂停',
        description: '统一控制帖子、评论、组局、资料修改和图片上传。',
        note: '关闭仅暂停新提交，已发布内容仍可浏览。',
      },
      {
        key: 'moderation_enabled', title: '内容审核', onLabel: '审核中', offLabel: '直接公开',
        description: '控制新帖子、评论和组局的自动审核与人工复核流程。',
        note: '关闭后新内容直接公开，硬违规词仍会拦截；已有待审内容保持原状态。',
      },
      {
        key: 'sensitive_words_enabled', title: '敏感词库', onLabel: '已启用', offLabel: '已停用',
        description: '硬违规词直接拒绝，灰度词在审核开启时转人工复核。',
        note: '词条的新增、编辑和删除仍在“敏感词库”页面管理。',
      },
    ],
  },
  {
    index: '02', title: '账号与权限', caption: '决定内测用户的准入与操作范围',
    items: [
      {
        key: 'registration_enabled', title: '新用户注册', onLabel: '开放', offLabel: '关闭',
        description: '控制网页端新账号注册，不影响已有账号登录和退出。',
      },
      {
        key: 'guest_posting_enabled', title: '游客发布', onLabel: '允许', offLabel: '仅认证学生',
        description: '允许已登录但未完成学籍认证的账号发布帖子和组局。',
        note: '游客仍需登录；冻结账号和管理员权限不受此开关影响。',
      },
      {
        key: 'guest_interaction_enabled', title: '游客互动', onLabel: '允许', offLabel: '仅认证学生',
        description: '允许未认证账号评论、点赞、收藏、关注和报名组局。',
      },
    ],
  },
]

const load = async () => {
  loading.value = true
  try {
    Object.assign(controls, await getRuntimeControls())
  } catch { /* 拦截器已提示 */ } finally {
    loading.value = false
  }
}

const confirmationFor = (item: ControlItem, value: boolean): string | null => {
  if (item.key === 'publishing_enabled' && !value) {
    return '关闭后，用户将无法发布帖子、评论、组局或上传图片。已发布内容仍可浏览。确定暂停吗？'
  }
  if (item.key === 'moderation_enabled' && !value) {
    return '关闭后，新帖子、评论和组局将跳过审核并直接公开。启用中的硬违规词仍会拦截，已有待审内容不会自动通过。确定关闭吗？'
  }
  if (item.key === 'sensitive_words_enabled' && !value) {
    return '关闭后，敏感词库将不再参与新提交内容及待审任务的判定。确定停用吗？'
  }
  if (item.key === 'registration_enabled' && !value) {
    return '关闭后，新用户无法注册；已有账号仍可正常登录。确定关闭注册吗？'
  }
  if (item.key === 'guest_posting_enabled' && value) {
    return '开启后，未完成学籍认证的登录账号也能发布帖子和组局。确定开放吗？'
  }
  if (item.key === 'guest_interaction_enabled' && value) {
    return '开启后，未完成学籍认证的登录账号也能评论、点赞、收藏、关注和报名组局。确定开放吗？'
  }
  return null
}

const onSwitch = async (item: ControlItem, rawValue: string | number | boolean) => {
  const value = Boolean(rawValue)
  const confirmation = confirmationFor(item, value)
  if (confirmation) {
    try {
      await ElMessageBox.confirm(confirmation, `确认${value ? '开启' : '关闭'}${item.title}`, {
        type: 'warning', confirmButtonText: '确认变更', cancelButtonText: '取消',
      })
    } catch { return }
  }
  savingKey.value = item.key
  try {
    const latest = await updateRuntimeControls({ [item.key]: value })
    Object.assign(controls, latest)
    ElMessage.success(`${item.title}已${value ? '开启' : '关闭'}`)
  } catch { /* 保存失败时保留服务端原状态，拦截器已提示 */ } finally {
    savingKey.value = null
  }
}

onMounted(load)
</script>

<style scoped>
.controls-page { max-width: 1080px; margin: 0 auto; }
.control-hero {
  display: flex; align-items: flex-end; justify-content: space-between; gap: 24px;
  padding: 12px 4px 28px;
}
.eyebrow { color: var(--el-color-primary); font-size: 11px; font-weight: 700; letter-spacing: 2px; margin-bottom: 8px; }
h1 { color: var(--app-title-color); font-size: 30px; line-height: 1.2; font-weight: 700; letter-spacing: -1px; }
.control-hero p { color: var(--app-muted); font-size: 14px; line-height: 1.7; margin-top: 10px; }
.live-status {
  display: flex; align-items: center; gap: 8px; flex-shrink: 0; color: var(--app-muted);
  font-size: 13px; padding: 8px 12px; border: 1px solid var(--el-border-color-lighter);
  border-radius: 20px; background: var(--app-aside-bg);
}
.live-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--el-color-success); box-shadow: 0 0 0 4px var(--el-color-success-light-9, rgba(0, 122, 77, .1)); }
.risk-alert { margin-bottom: 18px; }
.control-sections { display: grid; gap: 18px; }
.control-section {
  background: var(--app-aside-bg); border: 1px solid var(--el-border-color-lighter);
  border-radius: 14px; overflow: hidden; box-shadow: var(--app-card-shadow);
}
.section-head {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  padding: 20px 24px; border-bottom: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-extra-light);
}
.section-head > div { display: flex; align-items: center; gap: 12px; }
.section-index { color: var(--el-color-primary); font-size: 12px; font-weight: 700; letter-spacing: 1px; }
h2 { color: var(--app-title-color); font-size: 16px; font-weight: 650; }
.section-caption { color: var(--app-muted); font-size: 12px; }
.control-row { display: flex; align-items: center; justify-content: space-between; gap: 28px; padding: 24px; }
.control-row + .control-row { border-top: 1px solid var(--el-border-color-lighter); }
.control-copy { min-width: 0; }
.control-title-line { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
h3 { color: var(--app-title-color); font-size: 15px; font-weight: 600; }
.state-label {
  color: var(--el-color-info); background: var(--el-fill-color-light); border-radius: 4px;
  padding: 2px 7px; font-size: 11px; line-height: 1.5;
}
.state-label.on { color: var(--el-color-success); background: var(--el-color-success-light-9, rgba(0, 122, 77, .1)); }
.control-row p { color: var(--app-muted); font-size: 13px; line-height: 1.7; margin-top: 7px; }
.control-note { display: block; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.6; margin-top: 5px; }
.control-row :deep(.el-switch) { flex-shrink: 0; }
.shortcut-section { padding: 24px 4px 8px; display: flex; align-items: flex-start; gap: 24px; }
.shortcut-title { color: var(--app-title-color); font-size: 13px; font-weight: 600; flex-shrink: 0; padding-top: 4px; }
.shortcut-links { display: flex; flex-wrap: wrap; gap: 10px 22px; }
.shortcut-links a { color: var(--app-muted); text-decoration: none; font-size: 13px; line-height: 1.7; }
.shortcut-links a:hover { color: var(--el-color-primary); }
.shortcut-links a span { color: var(--el-color-primary); margin-left: 3px; }

@media (max-width: 640px) {
  .control-hero { align-items: flex-start; flex-direction: column; padding-bottom: 20px; }
  h1 { font-size: 26px; }
  .section-head { align-items: flex-start; flex-direction: column; gap: 5px; padding: 17px 18px; }
  .control-row { padding: 20px 18px; gap: 16px; }
  .shortcut-section { flex-direction: column; gap: 10px; }
}
</style>
