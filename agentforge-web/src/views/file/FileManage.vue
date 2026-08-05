<script setup lang="ts">
/** 文件管理页：按智能体选择 → 上传文档 → 状态列表（轮询刷新）→ 删除/重试 */
import { onMounted, onUnmounted, ref, watch } from 'vue'
import AppLayout from '../../components/layout/AppLayout.vue'
import FileUpload from '../../components/common/FileUpload.vue'
import { apiDeleteFile, apiFileList, apiRetryFile } from '../../api/file'
import { useAgentStore } from '../../stores/agent'
import { notifyError, notifySuccess } from '../../utils/notify'
import type { DocumentItem } from '../../types/chat'

const agentStore = useAgentStore()

const agents = ref(agentStore.list)
const selectedAgentId = ref<number | null>(null)
const documents = ref<DocumentItem[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(10)
const loading = ref(false)
let timer: ReturnType<typeof setInterval> | null = null

const STATUS_TEXT: Record<DocumentItem['status'], string> = {
  PENDING: '等待处理',
  PROCESSING: '处理中',
  READY: '已入库',
  FAILED: '处理失败',
}

async function ensureAgents(): Promise<void> {
  if (!agents.value.length) {
    await agentStore.fetchList(1, 100)
    agents.value = agentStore.list
  }
}

async function loadDocs(): Promise<void> {
  if (!selectedAgentId.value) return
  loading.value = true
  try {
    const result = await apiFileList(selectedAgentId.value, { page: page.value, size: size.value })
    documents.value = result.list
    total.value = result.total
  } finally {
    loading.value = false
  }
}

function onAgentChange(): void {
  page.value = 1
  loadDocs()
}

async function onDelete(id: number): Promise<void> {
  if (!window.confirm('确认删除该文档？磁盘文件与知识库向量将一并删除。')) return
  try {
    await apiDeleteFile(id)
    notifySuccess('删除成功')
    loadDocs()
  } catch (e) {
    notifyError((e as Error).message)
  }
}

async function onRetry(id: number): Promise<void> {
  try {
    await apiRetryFile(id)
    notifySuccess('已重新入库')
    loadDocs()
  } catch (e) {
    notifyError((e as Error).message)
    loadDocs()
  }
}

// 状态轮询：存在非终态（PENDING/PROCESSING）时每 3s 刷新
watch(
  () => documents.value.map((d) => d.status).join(','),
  (statuses) => {
    const pending = /PENDING|PROCESSING/.test(statuses)
    if (pending && !timer) {
      timer = setInterval(loadDocs, 3000)
    } else if (!pending && timer) {
      clearInterval(timer)
      timer = null
    }
  },
)

onMounted(async () => {
  await ensureAgents()
  if (agents.value.length) {
    selectedAgentId.value = agents.value[0].id
    await loadDocs()
  }
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <AppLayout>
    <div class="page-container">
      <div class="page-header">
        <div>
          <div class="eyebrow">FILES · {{ total }}</div>
          <h2>文件管理</h2>
        </div>
        <FileUpload v-if="selectedAgentId" :agent-id="selectedAgentId" @uploaded="loadDocs" />
      </div>

      <div class="card">
        <div class="agent-select">
          <label>所属智能体：</label>
          <select v-model="selectedAgentId" class="select select-agent" @change="onAgentChange">
            <option v-for="agent in agents" :key="agent.id" :value="agent.id">
              {{ agent.name }}
            </option>
          </select>
        </div>

        <table class="table">
          <thead>
            <tr>
              <th>文件名</th>
              <th>类型</th>
              <th>状态</th>
              <th>上传时间</th>
              <th style="width: 160px">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="doc in documents" :key="doc.id">
              <td>{{ doc.fileName }}</td>
              <td class="muted mono">{{ doc.fileType }}</td>
              <td>
                <span class="badge" :class="`badge-${doc.status.toLowerCase()}`">
                  {{ STATUS_TEXT[doc.status] }}
                </span>
              </td>
              <td class="muted">{{ new Date(doc.createdTime).toLocaleString() }}</td>
              <td>
                <button
                  v-if="doc.status === 'FAILED' || doc.status === 'PENDING'"
                  class="btn btn-secondary btn-sm"
                  @click="onRetry(doc.id)"
                >
                  重试
                </button>
                <button class="btn btn-danger btn-sm" @click="onDelete(doc.id)">删除</button>
              </td>
            </tr>
            <tr v-if="!loading && documents.length === 0">
              <td colspan="5" class="muted" style="text-align: center; padding: 32px">
                暂无文档，点击右上角「上传文档」入库知识库
              </td>
            </tr>
          </tbody>
        </table>

        <div class="pagination">
          <span class="muted">共 {{ total }} 条</span>
          <button class="btn btn-secondary btn-sm" :disabled="page <= 1" @click="page--; loadDocs()">
            上一页
          </button>
          <span>第 {{ page }} 页</span>
          <button
            class="btn btn-secondary btn-sm"
            :disabled="page * size >= total"
            @click="page++; loadDocs()"
          >
            下一页
          </button>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
.agent-select {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 14px;
}

.select-agent {
  width: 220px;
}

td .btn {
  margin-right: 6px;
}
</style>
