<template>
  <el-card shadow="never">
    <template #header>
      <div class="card-head">
        <span>标签库（发布页热搜标签）</span>
        <el-button type="primary" @click="showCreate = true">＋ 新建标签</el-button>
      </div>
    </template>

    <el-table :data="items" v-loading="loading">
      <el-table-column label="ID" prop="id" width="80" />
      <el-table-column label="标签名" min-width="180">
        <template #default="{ row }">#{{ row.name }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button link type="danger" size="small" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!items.length && !loading" description="暂无标签" />

    <el-dialog v-model="showCreate" title="新建标签" width="420px">
      <el-form label-width="70px">
        <el-form-item label="标签名">
          <el-input v-model="form.name" maxlength="30" placeholder="1-30 字，如：考研交流" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onCreate">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getAdminTags, createAdminTag, deleteAdminTag, type AdminTag } from '@/api/tags'

const items = ref<AdminTag[]>([])
const loading = ref(false)
const showCreate = ref(false)
const saving = ref(false)
const form = reactive({ name: '' })

const load = async () => {
  loading.value = true
  try {
    const data = await getAdminTags()
    items.value = data.items
  } catch { /* 拦截器已提示 */ } finally {
    loading.value = false
  }
}

const onCreate = async () => {
  const name = form.name.trim()
  if (!name) {
    ElMessage.warning('标签名不能为空')
    return
  }
  saving.value = true
  try {
    await createAdminTag(name)
    ElMessage.success('创建成功')
    showCreate.value = false
    form.name = ''
    load()
  } catch { /* 拦截器已提示 */ } finally {
    saving.value = false
  }
}

const onDelete = async (row: AdminTag) => {
  await ElMessageBox.confirm(`确定删除标签「#${row.name}」吗？关联帖子会同步解除绑定。`, '确认', { type: 'warning' })
  await deleteAdminTag(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(() => load())
</script>

<style scoped>
.card-head { display: flex; align-items: center; justify-content: space-between; }
</style>
