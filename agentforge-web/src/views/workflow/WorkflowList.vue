<script setup lang="ts">
/** 工作流列表：创建 / 编辑 / 删除（M3 Workflow v1） */
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { apiDeleteWorkflow, apiWorkflowPage } from '../../api/workflow'
import { notifyError, notifySuccess } from '../../utils/notify'
import type { Workflow } from '../../types/workflow'

const router = useRouter()
const list = ref<Workflow[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(10)
const loading = ref(false)

async function load(): Promise<void> {
  loading.value = true
  try {
    const result = await apiWorkflowPage({ page: page.value, size: size.value })
    list.value = result.list
    total.value = result.total
  } catch (e) {
    notifyError((e as Error).message)
  } finally {
    loading.value = false
  }
}

function goCreate(): void {
  router.push('/workflows/new')
}

function goEdit(id: number): void {
  router.push(`/workflows/${id}/edit`)
}

async function onDelete(id: number, name: string): Promise<void> {
  if (!window.confirm(`确认删除工作流「${name}」？此操作不可恢复。`)) return
  try {
    await apiDeleteWorkflow(id)
    notifySuccess('删除成功')
    if (list.value.length === 1 && page.value > 1) page.value -= 1
    load()
  } catch (e) {
    notifyError((e as Error).message)
  }
}

onMounted(load)
</script>

<template>
  <AppLayout>
    <div class="page-container">
      <div class="page-header">
        <h2>工作流</h2>
        <button class="btn" @click="goCreate">+ 新建工作流</button>
      </div>

      <div v-if="loading" class="muted">加载中…</div>
      <div v-else-if="!list.length" class="card muted empty-tip">
        暂无工作流。创建流程后可将智能体切换为「工作流模式」：聊天消息作为流程输入 {message}，
        答案取流程最终输出（如「查仓库 → 算指标 → 生成报告」）。
      </div>
      <div v-else class="card">
        <table class="table">
          <thead>
            <tr>
              <th>名称</th>
              <th>描述</th>
              <th>节点数</th>
              <th>状态</th>
              <th class="col-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="wf in list" :key="wf.id">
              <td>{{ wf.name }}</td>
              <td class="muted">{{ wf.description || '-' }}</td>
              <td>{{ wf.nodes.length }}</td>
              <td>
                <span class="badge" :class="wf.status === 'ACTIVE' ? 'badge-ok' : 'badge-warn'">
                  {{ wf.status }}
                </span>
              </td>
              <td class="col-actions">
                <button class="btn btn-secondary btn-sm" @click="goEdit(wf.id)">编辑 / 运行</button>
                <button class="btn btn-danger btn-sm" @click="onDelete(wf.id, wf.name)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="pager">
          <button class="btn btn-secondary btn-sm" :disabled="page <= 1" @click="page--; load()">
            上一页
          </button>
          <span class="muted">第 {{ page }} 页 / 共 {{ total }} 条</span>
          <button
            class="btn btn-secondary btn-sm"
            :disabled="page * size >= total"
            @click="page++; load()"
          >
            下一页
          </button>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
.empty-tip {
  padding: 32px;
  line-height: 1.8;
}

.table {
  width: 100%;
  border-collapse: collapse;
}

.table th,
.table td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--color-border);
  text-align: left;
  font-size: 14px;
}

.col-actions {
  white-space: nowrap;
  width: 160px;
}

.col-actions .btn {
  margin-right: 6px;
}

.badge {
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
}

.badge-ok {
  background: rgba(34, 197, 94, 0.12);
  color: #16a34a;
}

.badge-warn {
  background: rgba(245, 158, 11, 0.12);
  color: #d97706;
}

.pager {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0 0;
}
</style>
