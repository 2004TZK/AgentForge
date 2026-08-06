<script setup lang="ts">
/** 工具库：自定义工具列表（我的 + 公开），新建 / 编辑 / 复制 / 删除 / 测试跳转 */
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { apiCopyToolDefinition, apiDeleteToolDefinition, apiToolDefinitionPage } from '../../api/toolDefinition'
import { notifyError, notifySuccess } from '../../utils/notify'
import type { ToolDefinition } from '../../types/toolDefinition'

const router = useRouter()
const list = ref<ToolDefinition[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(10)
const keyword = ref('')
const loading = ref(false)

async function load(): Promise<void> {
  loading.value = true
  try {
    const result = await apiToolDefinitionPage({ page: page.value, size: size.value, keyword: keyword.value })
    list.value = result.list
    total.value = result.total
  } catch (e) {
    notifyError((e as Error).message)
  } finally {
    loading.value = false
  }
}

function goCreate(): void {
  router.push('/tools/new')
}

function goEdit(id: number): void {
  router.push(`/tools/${id}/edit`)
}

async function onCopy(id: number, name: string): Promise<void> {
  if (!window.confirm(`复制工具「${name}」到我的工具库？`)) return
  try {
    await apiCopyToolDefinition(id)
    notifySuccess('复制成功')
    load()
  } catch (e) {
    notifyError((e as Error).message)
  }
}

async function onDelete(id: number, name: string): Promise<void> {
  if (!window.confirm(`确认删除工具「${name}」？此操作不可恢复。`)) return
  try {
    await apiDeleteToolDefinition(id)
    notifySuccess('删除成功')
    if (list.value.length === 1 && page.value > 1) page.value -= 1
    load()
  } catch (e) {
    notifyError((e as Error).message)
  }
}

function onSearch(): void {
  page.value = 1
  load()
}

onMounted(load)
</script>

<template>
  <AppLayout>
    <div class="page-container">
      <div class="page-header">
        <div>
          <div class="eyebrow">TOOL LIBRARY · {{ total }}</div>
          <h2>工具库</h2>
        </div>
        <button class="btn" @click="goCreate">+ 新建工具</button>
      </div>

      <div class="card search-row">
        <input
          v-model="keyword"
          class="input"
          placeholder="按工具名搜索"
          @keyup.enter="onSearch"
        />
        <button class="btn btn-secondary btn-sm" @click="onSearch">搜索</button>
      </div>

      <div v-if="loading" class="muted">加载中…</div>
      <div v-else-if="!list.length" class="card muted empty-tip">
        暂无自定义工具。创建 HTTP 工具（调用外部 API）或代码工具（数据清洗/文本处理等逻辑），
        再到智能体编辑页绑定即可被 LLM 自主调用。
      </div>
      <div v-else class="card">
        <table class="table">
          <thead>
            <tr>
              <th>名称</th>
              <th>类型</th>
              <th>描述</th>
              <th>可见性</th>
              <th>参数数</th>
              <th class="col-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="tool in list" :key="tool.id">
              <td>
                <span class="mono tool-name">{{ tool.name }}</span>
                <span class="muted display-name">{{ tool.displayName }}</span>
              </td>
              <td>
                <span class="badge" :class="tool.toolType === 'http' ? 'badge-ok' : 'badge-warn'">
                  {{ tool.toolType === 'http' ? 'HTTP' : '代码' }}
                </span>
              </td>
              <td class="muted desc">{{ tool.description || '-' }}</td>
              <td>
                <span class="badge" :class="tool.visibility === 'PUBLIC' ? 'badge-ok' : ''">
                  {{ tool.visibility }}
                </span>
              </td>
              <td class="mono">
                {{ Object.keys((tool.parameters as Record<string, unknown>)?.properties ?? {}).length }}
              </td>
              <td class="col-actions">
                <button class="btn btn-secondary btn-sm" @click="goEdit(tool.id)">编辑 / 测试</button>
                <button class="btn btn-secondary btn-sm" @click="onCopy(tool.id, tool.displayName)">复制</button>
                <button class="btn btn-danger btn-sm" @click="onDelete(tool.id, tool.displayName)">删除</button>
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
.search-row {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  margin-bottom: 12px;
}

.search-row .input {
  flex: 1;
  max-width: 320px;
}

.empty-tip {
  padding: 32px;
  line-height: 1.8;
  text-align: left;
}

.tool-name {
  font-weight: 600;
}

.display-name {
  margin-left: 8px;
  font-size: 12px;
}

.desc {
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
