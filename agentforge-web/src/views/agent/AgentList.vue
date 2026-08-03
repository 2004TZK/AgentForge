<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { useAgentStore } from '../../stores/agent'
import { useAuthStore } from '../../stores/auth'
import { notifyError, notifySuccess } from '../../utils/notify'

const router = useRouter()
const agentStore = useAgentStore()
const authStore = useAuthStore()

const keyword = ref('')
const page = ref(1)
const size = ref(10)

async function load(): Promise<void> {
  await agentStore.fetchList(page.value, size.value, keyword.value.trim())
}

function search(): void {
  page.value = 1
  load()
}

function goCreate(): void {
  router.push('/agents/new')
}

function goEdit(id: number): void {
  router.push(`/agents/${id}/edit`)
}

function goChat(id: number): void {
  router.push(`/chat/${id}`)
}

async function onDelete(id: number): Promise<void> {
  if (!window.confirm('确认删除该智能体？此操作不可恢复。')) return
  try {
    await agentStore.remove(id)
    notifySuccess('删除成功')
    // 删除后回退一页（避免当前页为空）
    if (agentStore.list.length === 1 && page.value > 1) page.value -= 1
    load()
  } catch (e) {
    notifyError((e as Error).message)
  }
}

const isOwner = (creatorId: number): boolean => authStore.user?.id === creatorId

onMounted(load)
</script>

<template>
  <AppLayout>
    <div class="page-container">
      <div class="page-header">
        <h2>智能体</h2>
        <button class="btn" @click="goCreate">+ 新建智能体</button>
      </div>

      <div class="card">
        <div class="toolbar">
          <input
            v-model="keyword"
            class="input search-input"
            placeholder="按名称搜索"
            @keyup.enter="search"
          />
          <button class="btn btn-secondary" @click="search">搜索</button>
        </div>

        <table class="table">
          <thead>
            <tr>
              <th>名称</th>
              <th>描述</th>
              <th>模型</th>
              <th>温度</th>
              <th>创建时间</th>
              <th style="width: 200px">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="agent in agentStore.list" :key="agent.id">
              <td>
                <strong>{{ agent.name }}</strong>
                <span v-if="!isOwner(agent.creatorId)" class="muted"> · 他人创建</span>
              </td>
              <td class="muted ellipsis">{{ agent.description || '-' }}</td>
              <td>{{ agent.modelName }}</td>
              <td>{{ agent.temperature }}</td>
              <td class="muted">{{ new Date(agent.createdTime).toLocaleString() }}</td>
              <td>
                <button class="btn btn-secondary btn-sm" @click="goChat(agent.id)">聊天</button>
                <button class="btn btn-secondary btn-sm" @click="goEdit(agent.id)">编辑</button>
                <button
                  v-if="isOwner(agent.creatorId)"
                  class="btn btn-danger btn-sm"
                  @click="onDelete(agent.id)"
                >
                  删除
                </button>
              </td>
            </tr>
            <tr v-if="!agentStore.loading && agentStore.list.length === 0">
              <td colspan="6" class="muted" style="text-align: center; padding: 32px">
                暂无智能体，点击右上角「新建智能体」开始创建
              </td>
            </tr>
          </tbody>
        </table>

        <div class="pagination">
          <span class="muted">共 {{ agentStore.total }} 条</span>
          <button class="btn btn-secondary btn-sm" :disabled="page <= 1" @click="page--; load()">
            上一页
          </button>
          <span>第 {{ page }} 页</span>
          <button
            class="btn btn-secondary btn-sm"
            :disabled="page * size >= agentStore.total"
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
.toolbar {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
}

.search-input {
  max-width: 260px;
}

.ellipsis {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

td .btn {
  margin-right: 6px;
}
</style>
