<script setup lang="ts">
/** 文件上传组件：选择文件 → 调上传接口（multipart）→ 回调结果 */
import { ref } from 'vue'
import { apiUploadFile } from '../../api/file'
import { notifyError } from '../../utils/notify'
import type { DocumentItem } from '../../types/chat'

const props = defineProps<{ agentId: number }>()
const emit = defineEmits<{ uploaded: [doc: DocumentItem] }>()

const fileInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const progress = ref(0)

async function onFileChange(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !props.agentId) {
    notifyError('请先选择智能体')
    return
  }
  uploading.value = true
  progress.value = 0
  try {
    const doc = await apiUploadFile(props.agentId, file, (percent) => {
      progress.value = percent
    })
    emit('uploaded', doc)
  } catch {
    // 错误提示已由拦截器处理
  } finally {
    uploading.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

function trigger(): void {
  fileInput.value?.click()
}
</script>

<template>
  <div class="upload">
    <input ref="fileInput" type="file" accept=".pdf,.docx,.txt,.md" hidden @change="onFileChange" />
    <button class="btn" :disabled="uploading || !agentId" @click="trigger">
      {{ uploading ? `上传中 ${progress}%…` : '上传文档' }}
    </button>
    <span class="muted upload-tip">支持 pdf / docx / txt / md，≤ 20MB，上传后自动入库知识库</span>
  </div>
</template>

<style scoped>
.upload {
  display: flex;
  align-items: center;
  gap: 12px;
}

.upload-tip {
  font-size: 12px;
}
</style>
