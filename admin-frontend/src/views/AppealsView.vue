<template>
  <el-card shadow="never">
    <template #header>内容与认证申诉</template>
    <el-alert title="接受申诉只记录复核结论。恢复内容或重新核验需在对应审核页面确认，不能绕过状态校验。" :closable="false" />
    <el-space style="margin:20px 0">
      <el-select v-model="status" style="width:150px" @change="page = 1; load()">
        <el-option label="待处理" value="pending"/><el-option label="已接受" value="accepted"/><el-option label="已拒绝" value="rejected"/>
      </el-select>
      <el-button @click="load">刷新</el-button>
    </el-space>
    <el-table :data="items">
      <el-table-column prop="entity_type" label="类型" width="120"/>
      <el-table-column prop="entity_id" label="对象编号"/>
      <el-table-column prop="reason" label="申诉理由"/>
      <el-table-column prop="decision_reason" label="处理说明"/>
      <el-table-column label="操作" width="150" fixed="right"><template #default="{row}">
        <el-button v-if="row.status === 'pending'" link type="primary" @click="decide(row as Appeal,'accepted')">接受</el-button>
        <el-button v-if="row.status === 'pending'" link type="danger" @click="decide(row as Appeal,'rejected')">拒绝</el-button>
      </template></el-table-column>
    </el-table>
    <el-pagination v-model:current-page="page" :total="total" :page-size="20" layout="total,prev,pager,next" @current-change="load"/>
  </el-card>
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import request from '@/utils/request'
interface Appeal { id:string; entity_type:string; entity_id:string; reason:string; status:string; decision_reason:string|null }
const items = ref<Appeal[]>([]), page = ref(1), total = ref(0), status = ref('pending')
async function load() {
  try {
    const data = await request.get<never,{items:Appeal[];total:number}>('/admin/appeals',{params:{status:status.value,page:page.value}})
    items.value = data.items; total.value = data.total
  } catch { /* 拦截器已提示 */ }
}
async function decide(row: Appeal, decision: string) {
  let answer: string
  try {
    const result = await ElMessageBox.prompt('填写复核说明；不要录入姓名、学号等敏感信息','处理申诉',{inputValidator:(value:string)=>value.trim().length>=5||'至少五个字'})
    answer = result.value
  } catch {
    return // 用户取消：静默处理，不发请求、不提示
  }
  try {
    await request.post(`/admin/appeals/${row.id}/decision`,{decision,reason:answer})
    await load()
  } catch {
    // 拦截器已提示错误；保留列表与重试能力
  }
}
onMounted(load)
</script>
