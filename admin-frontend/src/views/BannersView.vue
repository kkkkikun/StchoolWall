<template>
  <el-card shadow="never">
    <template #header>
      <div class="header-row">
        <span>首页轮播广告</span>
        <el-button type="primary" @click="openForm()">＋ 新建广告</el-button>
      </div>
    </template>

    <el-table :data="items" v-loading="loading">
      <el-table-column label="预览" width="140">
        <template #default="{ row }">
          <el-image v-if="row.image_url" :src="row.image_url" fit="cover"
                    class="banner-thumb" :preview-src-list="[row.image_url]" preview-teleported />
          <div v-else class="banner-thumb banner-grad">🎨</div>
        </template>
      </el-table-column>
      <el-table-column label="标题" min-width="160">
        <template #default="{ row }">
          <span>{{ row.title }}</span>
          <el-tag v-if="row.tag" size="small" class="tag-chip">{{ row.tag }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="描述" min-width="160">
        <template #default="{ row }">{{ row.desc || '—' }}</template>
      </el-table-column>
      <el-table-column label="跳转" min-width="140">
        <template #default="{ row }">
          <span v-if="row.post_id">帖子 #{{ row.post_id }}</span>
          <span v-else-if="row.activity_id">活动 #{{ activityName(row.activity_id) }}</span>
          <span v-else-if="row.link_url" class="link-text">{{ row.link_url }}</span>
          <span v-else class="muted">未设置</span>
        </template>
      </el-table-column>
      <el-table-column label="权重" prop="sort" width="70" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
            {{ row.status === 1 ? '投放中' : '已下架' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="投放期" width="200">
        <template #default="{ row }">
          <span class="muted">{{ fmtRange(row) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link :type="row.status === 1 ? 'warning' : 'success'" size="small" @click="onToggle(row)">
            {{ row.status === 1 ? '下架' : '上架' }}
          </el-button>
          <el-button link type="primary" size="small" @click="openForm(row)">编辑</el-button>
          <el-button link type="danger" size="small" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!items.length && !loading" description="暂无轮播广告" />

    <!-- 新建/编辑 -->
    <el-dialog v-model="showForm" :title="editing ? '编辑广告' : '新建广告'" width="560px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" maxlength="50" show-word-limit />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.desc" maxlength="100" />
        </el-form-item>
        <el-form-item label="角标">
          <el-input v-model="form.tag" maxlength="10" placeholder="活动 / 热门 …" style="width: 160px" />
        </el-form-item>
        <el-form-item label="排序权重">
          <el-input-number v-model="form.sort" :min="0" :max="999" />
          <span class="hint">越大越靠前</span>
        </el-form-item>
        <el-form-item label="图片">
          <div class="upload-row">
            <el-upload :show-file-list="false" accept="image/*" :http-request="onUpload" :disabled="uploading">
              <el-button :loading="uploading">{{ uploading ? '上传中…' : '上传图片' }}</el-button>
            </el-upload>
            <el-input v-if="form.image_url" v-model="form.image_url" class="url-input" placeholder="图片 URL" />
          </div>
          <div class="hint">不传图则首页走渐变文案样式</div>
        </el-form-item>
        <el-form-item label="跳转帖子 ID">
          <el-input-number v-model="form.post_id" :min="1" controls-position="right" style="width: 140px" />
          <span class="hint">与活动/外链三选一</span>
        </el-form-item>
        <el-form-item label="站内活动">
          <el-select v-model="form.activity_id" clearable filterable placeholder="选择活动页" style="width: 260px">
            <el-option v-for="a in activities" :key="a.id" :label="`#${a.id} ${a.title}`" :value="a.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="外链 URL">
          <el-input v-model="form.link_url" placeholder="https://…" />
        </el-form-item>
        <el-form-item label="投放期">
          <el-date-picker v-model="form.range" type="datetimerange" value-format="YYYY-MM-DDTHH:mm:ss[Z]"
                          start-placeholder="开始（可空）" end-placeholder="结束（可空）" style="width: 340px" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showForm = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getBanners, createBanner, updateBanner, deleteBanner, uploadImage, type AdminBanner } from '@/api/banners'
import { getActivities, type AdminActivity } from '@/api/activities'

const items = ref<AdminBanner[]>([])
const activities = ref<AdminActivity[]>([])
const loading = ref(false)

const showForm = ref(false)
const saving = ref(false)
const uploading = ref(false)
const editing = ref<AdminBanner | null>(null)

const form = reactive({
  title: '', desc: '', tag: '', sort: 0,
  image_url: '', post_id: undefined as number | undefined, activity_id: undefined as number | undefined, link_url: '',
  range: null as [string, string] | null,
})

const fmtRange = (row: AdminBanner) => {
  const s = row.start_at ? row.start_at.slice(0, 10) : '立即'
  const e = row.end_at ? row.end_at.slice(0, 10) : '永久'
  return `${s} ~ ${e}`
}

const load = async () => {
  loading.value = true
  try {
    const [banners, acts] = await Promise.all([getBanners(), getActivities({ page: 1, page_size: 100 })])
    items.value = banners.items
    activities.value = acts.items
  } catch { /* 拦截器已提示 */ } finally {
    loading.value = false
  }
}

const openForm = (row?: AdminBanner) => {
  editing.value = row || null
  form.title = row?.title || ''
  form.desc = row?.desc || ''
  form.tag = row?.tag || ''
  form.sort = row?.sort ?? 0
  form.image_url = row?.image_url || ''
  form.post_id = row?.post_id || undefined
  form.activity_id = row?.activity_id || undefined
  form.link_url = row?.link_url || ''
  form.range = (row?.start_at && row?.end_at) ? [row.start_at, row.end_at] : null
  showForm.value = true
}

const activityName = (id: number) => activities.value.find(a => a.id === id)?.title || `#${id}`

const onUpload = async (option: any) => {
  uploading.value = true
  try {
    const result = await uploadImage(option.file as File)
    form.image_url = result.public_url
    ElMessage.success('上传成功')
  } catch { /* 拦截器已提示 */ } finally {
    uploading.value = false
  }
}

const save = async () => {
  if (!form.title.trim()) {
    ElMessage.warning('标题必填')
    return
  }
  const targetCount = [form.post_id, form.activity_id, form.link_url].filter(Boolean).length
  if (targetCount > 1) {
    ElMessage.warning('帖子 / 活动 / 外链只能三选一')
    return
  }
  const data: Record<string, unknown> = {
    title: form.title.trim(),
    desc: form.desc.trim() || null,
    tag: form.tag.trim() || null,
    sort: form.sort,
    image_url: form.image_url.trim() || null,
    post_id: form.post_id || null,
    activity_id: form.activity_id || null,
    link_url: form.link_url.trim() || null,
    start_at: form.range ? form.range[0] : null,
    end_at: form.range ? form.range[1] : null,
  }
  saving.value = true
  try {
    if (editing.value) await updateBanner(editing.value.id, data)
    else await createBanner(data)
    ElMessage.success('保存成功')
    showForm.value = false
    load()
  } catch { /* 拦截器已提示 */ } finally {
    saving.value = false
  }
}

const onToggle = async (row: AdminBanner) => {
  await updateBanner(row.id, { status: row.status === 1 ? 0 : 1 })
  load()
}

const onDelete = async (row: AdminBanner) => {
  await ElMessageBox.confirm(`确定删除广告「${row.title}」吗？`, '删除', { type: 'warning' })
  await deleteBanner(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(() => load())
</script>

<style scoped>
.header-row { display: flex; justify-content: space-between; align-items: center; }
.banner-thumb { width: 120px; height: 60px; border-radius: 6px; }
.banner-grad {
  display: flex; align-items: center; justify-content: center;
  background: var(--app-brand-grad); font-size: 22px;
}
.tag-chip { margin-left: 8px; }
.link-text { color: var(--el-color-primary); font-size: 12px; }
.muted { color: var(--el-text-color-secondary); font-size: 12px; }
.hint { font-size: 12px; color: var(--el-text-color-placeholder); margin-left: 8px; }
.upload-row { display: flex; gap: 12px; align-items: center; width: 100%; }
.url-input { flex: 1; }
</style>
