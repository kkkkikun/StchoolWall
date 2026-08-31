<template>
  <el-dialog :model-value="modelValue" title="修改密码" width="420px" @update:model-value="emit('update:modelValue', $event)">
    <el-form :model="form" label-width="80px">
      <el-form-item label="原密码">
        <el-input v-model="form.old" type="password" show-password />
      </el-form-item>
      <el-form-item label="新密码">
        <el-input v-model="form.new" type="password" show-password placeholder="至少 8 位" />
      </el-form-item>
      <el-form-item label="确认新密">
        <el-input v-model="form.confirm" type="password" show-password />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="loading" @click="onSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { changePassword } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>()

const router = useRouter()
const auth = useAuthStore()
const form = reactive({ old: '', new: '', confirm: '' })
const loading = ref(false)

const onSave = async () => {
  if (!form.old || !form.new) {
    ElMessage.warning('请填写完整')
    return
  }
  if (form.new.length < 8) {
    ElMessage.warning('新密码至少 8 位')
    return
  }
  if (form.new !== form.confirm) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  loading.value = true
  try {
    await changePassword(form.old, form.new)
    ElMessage.success('密码已修改，请重新登录')
    emit('update:modelValue', false)
    auth.logout()
    router.push('/login')
  } catch {
    /* 拦截器已提示 */
  } finally {
    loading.value = false
  }
}
</script>
