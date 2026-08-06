<script setup lang="ts">
/** 工具库：自定义工具列表（我的 + 公开），新建 / 编辑 / 复制 / 删除 / 测试跳转 */
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { apiToolsMeta } from '../../api/agent'
import { apiCopyToolDefinition, apiDeleteToolDefinition, apiToolDefinitionPage } from '../../api/toolDefinition'
import { notifyError, notifySuccess } from '../../utils/notify'
import type { ToolMeta } from '../../types/agent'
import type { ToolDefinition } from '../../types/toolDefinition'

const router = useRouter()
const list = ref<ToolDefinition[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(10)
const keyword = ref('')
const loading = ref(false)
/** 系统内置工具（只读展示 Schema/填写信息） */
const builtinTools = ref<ToolMeta[]>([])
const expandedBuiltin = ref<string | null>(null)

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

async function loadBuiltin(): Promise<void> {
  try {
    builtinTools.value = await apiToolsMeta()
  } catch {
    /* 内置工具元数据不可用时不展示 */
  }
}

function toggleBuiltin(name: string): void {
  expandedBuiltin.value = expandedBuiltin.value === name ? null : name
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

onMounted(() => {
  load()
  loadBuiltin()
})
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

      <!-- 系统内置工具（只读查看填写信息） -->
      <div class="card">
        <div class="section-title">
          <span class="section-key">BUILT-IN</span>系统内置工具
          <span class="muted">— 在「编辑智能体」页绑定后即可被 LLM 调用，此处可查看各工具的填写信息</span>
        </div>
        <div v-if="!builtinTools.length" class="muted">内置工具元数据加载中…</div>
        <table v-else class="table">
          <thead>
            <tr>
              <th>名称</th>
              <th>描述</th>
              <th>LLM 参数</th>
              <th>配置项</th>
              <th class="col-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="tool in builtinTools" :key="tool.name">
              <td class="mono tool-name">{{ tool.name }}</td>
              <td class="muted desc">{{ tool.description || '-' }}</td>
              <td class="mono">{{ Object.keys(tool.parameters ?? {}).length }}</td>
              <td class="mono">{{ Object.keys(tool.config ?? {}).length }}</td>
              <td class="col-actions">
                <button class="btn btn-secondary btn-sm" @click="toggleBuiltin(tool.name)">
                  {{ expandedBuiltin === tool.name ? '收起' : '查看填写信息' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>

        <div v-if="expandedBuiltin" class="builtin-detail">
          <template v-for="tool in builtinTools" :key="tool.name">
            <div v-if="tool.name === expandedBuiltin">
              <h4 class="mono">{{ tool.name }}</h4>
              <p class="muted">{{ tool.description || '暂无描述' }}</p>

              <div class="detail-label">LLM 调用参数 <span class="muted">— 模型自主填充，无需手动填写</span></div>
              <table v-if="Object.keys(tool.parameters ?? {}).length" class="table detail-table">
                <thead>
                  <tr><th>参数名</th><th>类型</th><th>必填</th><th>说明</th></tr>
                </thead>
                <tbody>
                  <tr v-for="(spec, param) in tool.parameters" :key="param">
                    <td class="mono">{{ param }}</td>
                    <td class="mono">{{ spec.type }}</td>
                    <td>{{ spec.required === false ? '否' : '是' }}</td>
                    <td class="muted">{{ spec.description || '-' }}</td>
                  </tr>
                </tbody>
              </table>
              <p v-else class="muted small-tip">该工具无需调用参数</p>

              <div class="detail-label">智能体配置项 <span class="muted">— 在编辑智能体页 TOOLS 区块填写，存 tool_config</span></div>
              <table v-if="Object.keys(tool.config ?? {}).length" class="table detail-table">
                <thead>
                  <tr><th>字段</th><th>类型</th><th>必填</th><th>默认值</th><th>说明</th></tr>
                </thead>
                <tbody>
                  <tr v-for="(spec, field) in tool.config" :key="field">
                    <td class="mono">{{ field }}</td>
                    <td class="mono">{{ spec.type }}</td>
                    <td>{{ spec.required ? '必填' : '可选' }}</td>
                    <td class="mono">{{ spec.default === undefined ? '-' : String(spec.default) }}</td>
                    <td class="muted">{{ spec.description || '-' }}</td>
                  </tr>
                </tbody>
              </table>
              <p v-else class="muted small-tip">该工具无需额外配置</p>
            </div>
          </template>
        </div>
      </div>

      <div class="section-title">
        <span class="section-key">CUSTOM</span>我的自定义工具
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

.section-title {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin: 16px 0 10px;
  font-weight: 600;
}

.section-title .muted {
  font-weight: 400;
  font-size: 12px;
}

.builtin-detail {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--line);
}

.builtin-detail h4 {
  margin: 0 0 4px;
  font-size: 15px;
}

.builtin-detail > p {
  margin: 0 0 12px;
  font-size: 13px;
}

.detail-label {
  margin: 12px 0 6px;
  font-size: 13px;
  font-weight: 600;
}

.detail-table {
  font-size: 12.5px;
}

.detail-table th,
.detail-table td {
  padding: 5px 8px;
}

.small-tip {
  font-size: 12px;
}
</style>
