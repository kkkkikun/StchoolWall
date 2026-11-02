<script setup lang="ts">
/** 发布帖子。图片走上传接口拿 media_id，再随发帖提交。 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { getTags, uploadImage } from '@/api/content'
import { createPost } from '@/api/posts'
import type { TagItem } from '@/api/types'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const POST_TYPES = [
  { value: 'general', label: '闲聊' },
  { value: 'second_hand', label: '二手交易' },
  { value: 'lost_found', label: '失物招领' },
  { value: 'carpool', label: '拼车' },
]

const MAX_IMAGES = 6
const MAX_CONTENT = 2000

const postType = ref('general')
const content = ref('')
const price = ref<number | undefined>(undefined)
const tagIds = ref<number[]>([])
const tags = ref<TagItem[]>([])
const images = ref<{ mediaId: string; preview: string }[]>([])
const submitting = ref(false)
const uploading = ref(false)

const typeOptions = POST_TYPES
const showPrice = computed(() => postType.value === 'second_hand')

async function pickFiles(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  input.value = ''
  if (!files.length) return
  const room = MAX_IMAGES - images.value.length
  if (room <= 0) {
    ElMessage.warning(`最多上传 ${MAX_IMAGES} 张图片`)
    return
  }
  uploading.value = true
  try {
    for (const file of files.slice(0, room)) {
      const result = await uploadImage(file, 'posts')
      images.value.push({ mediaId: result.media_id, preview: URL.createObjectURL(file) })
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '上传失败')
  } finally {
    uploading.value = false
  }
}

function removeImage(index: number): void {
  images.value.splice(index, 1)
}

async function submit(): Promise<void> {
  if (!content.value.trim()) {
    ElMessage.warning('正文不能为空')
    return
  }
  submitting.value = true
  try {
    const payload = {
      post_type: postType.value,
      content: content.value.trim(),
      tag_ids: tagIds.value.length ? tagIds.value : undefined,
      media_ids: images.value.length ? images.value.map((image) => image.mediaId) : undefined,
      price: showPrice.value ? price.value : undefined,
    }
    const result = await createPost(payload)
    ElMessage.success(result.status === 1 ? '发布成功' : '发布成功，图片审核中')
    await router.push(`/post/${result.post_id}`)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '发布失败')
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  tags.value = await getTags().catch(() => [])
})
</script>

<template>
  <div class="sw-publish">
    <section class="sw-card sw-publish__card">
      <h3 class="sw-card__title">发布帖子</h3>

      <el-alert
        v-if="!auth.canPublish"
        class="sw-publish__alert"
        type="warning"
        :closable="false"
        title="当前账号还不能发布"
        description="新注册账号需要先完成学生身份认证；发布功能也可能被运营临时关闭。"
      />

      <el-form label-width="72px" class="sw-publish__form">
        <el-form-item label="版块">
          <el-radio-group v-model="postType">
            <el-radio-button v-for="option in typeOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="正文">
          <el-input
            v-model="content"
            type="textarea"
            :rows="6"
            :maxlength="MAX_CONTENT"
            show-word-limit
            placeholder="说点什么吧…"
          />
        </el-form-item>

        <el-form-item v-if="showPrice" label="价格">
          <el-input-number v-model="price" :min="0" :max="10000000" placeholder="元" />
        </el-form-item>

        <el-form-item label="标签">
          <el-select v-model="tagIds" multiple placeholder="最多 10 个标签" class="sw-publish__tags">
            <el-option v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.id" />
          </el-select>
        </el-form-item>

        <el-form-item label="图片">
          <div class="sw-publish__images">
            <div v-for="(image, index) in images" :key="image.mediaId" class="sw-publish__image">
              <img :src="image.preview" alt="待发布图片" />
              <button type="button" class="sw-publish__remove" @click="removeImage(index)">×</button>
            </div>
            <label v-if="images.length < MAX_IMAGES" class="sw-publish__add">
              <input type="file" accept="image/*" multiple hidden @change="pickFiles" />
              <span>{{ uploading ? '上传中…' : '+ 添加图片' }}</span>
            </label>
          </div>
          <p class="sw-muted">图片会先进入隔离区，审核通过后才会显示在帖子里。</p>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="submitting" @click="submit">发布</el-button>
        </el-form-item>
      </el-form>
    </section>
  </div>
</template>

<style scoped>
.sw-publish__card {
  padding: var(--sw-space-5);
}

.sw-publish__alert {
  margin-top: var(--sw-space-4);
}

.sw-publish__form {
  margin-top: var(--sw-space-4);
}

.sw-publish__tags {
  width: 100%;
}

.sw-publish__images {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sw-space-2);
}

.sw-publish__image {
  position: relative;
  width: 96px;
  height: 96px;
  border-radius: var(--sw-radius-sm);
  overflow: hidden;
}

.sw-publish__image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.sw-publish__remove {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 20px;
  height: 20px;
  border: none;
  border-radius: 50%;
  background: rgb(0 0 0 / 60%);
  color: #fff;
  cursor: pointer;
  line-height: 1;
}

.sw-publish__add {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 96px;
  height: 96px;
  border: 1px dashed var(--sw-border-strong);
  border-radius: var(--sw-radius-sm);
  color: var(--sw-text-secondary);
  cursor: pointer;
  font-size: var(--sw-text-sm);
}

.sw-publish__add:hover {
  border-color: var(--sw-primary);
  color: var(--sw-primary);
}
</style>
