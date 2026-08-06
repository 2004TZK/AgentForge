<script setup lang="ts">
/** 新建/编辑智能体：基础信息 + 运行模式（M3）+ 工具配置（按 Schema 渲染配置表单） */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { apiAgentDetail, apiToolsMeta } from '../../api/agent'
import { apiProviderList } from '../../api/provider'
import { apiToolDefinitionPage } from '../../api/toolDefinition'
import { apiWorkflowPage } from '../../api/workflow'
import { useAgentStore } from '../../stores/agent'
import { notifyError, notifySuccess } from '../../utils/notify'
import type { AgentPayload, AgentTool, ToolMeta } from '../../types/agent'
import type { Provider } from '../../types/provider'
import type { ToolDefinition } from '../../types/toolDefinition'
import type { Workflow } from '../../types/workflow'

const route = useRoute()
const router = useRouter()
const agentStore = useAgentStore()

const isEdit = computed(() => route.params.id !== undefined)
const agentId = computed(() => Number(route.params.id))

const name = ref('')
const description = ref('')
const systemPrompt = ref('')
const modelName = ref('qwen3.7-plus')
const temperature = ref(0.7)
/** M3 运行模式：chat 对话（LLM 工具循环） / workflow 工作流（消息作为 {message} 输入） */
const mode = ref<'chat' | 'workflow'>('chat')
/** M4 可见性：PUBLIC 公开（所有人可见）/ PRIVATE 私有（仅创建者可见） */
const visibility = ref<'PUBLIC' | 'PRIVATE'>('PRIVATE')
const workflowId = ref<number | null>(null)
const workflows = ref<Workflow[]>([])
const tools = ref<AgentTool[]>([{ toolName: 'calculator', toolConfig: {}, enabled: true }])
const toolMeta = ref<ToolMeta[]>([])
/** M5 我的自定义工具（/tool-definitions 分页加载） */
const customTools = ref<ToolDefinition[]>([])
/** M4 模型 Provider：provider 下拉 + 可用模型联动 */
const providers = ref<Provider[]>([])
const providerId = ref<number | null>(null)
const loading = ref(false)
const saving = ref(false)

/** 当前 Provider 的可用模型（未选择 Provider 时为空 → 自由输入） */
const providerModels = computed(() => {
  const p = providers.value.find((x) => x.id === providerId.value)
  return p?.models ?? []
})

/** 工具选项（M3：由 /tools/meta 动态加载；加载失败时退回内置列表） */
const toolOptions = computed(() =>
  toolMeta.value.length ? toolMeta.value.map((t) => t.name) : ['calculator', 'github'],
)

function metaOf(toolName: string): ToolMeta | undefined {
  return toolMeta.value.find((t) => t.name === toolName)
}

/** M5 自定义工具元信息（来源工具库定义） */
function customToolMeta(toolName: string): ToolDefinition | undefined {
  return customTools.value.find((c) => c.name === toolName)
}

function configParamOf(toolName: string): string[] {
  return Object.keys(metaOf(toolName)?.config ?? {})
}

/** 工具选择变化：按 Schema 初始化配置字段（保留已有值），再提交新工具名 */
function onToolChange(tool: AgentTool, newName: string): void {
  if (newName === tool.toolName) return
  const defaults: Record<string, unknown> = {}
  for (const param of configParamOf(newName)) {
    defaults[param] = tool.toolConfig[param] ?? ''
  }
  tool.toolConfig = defaults
  tool.toolName = newName
}

/** M5 来源切换：builtin ↔ custom 时重置工具名与配置（不同来源 Schema 不同） */
function onToolSourceChange(tool: AgentTool, newSource: 'builtin' | 'custom'): void {
  if (newSource === (tool.toolSource ?? 'builtin')) return
  tool.toolSource = newSource
  tool.toolDefinitionId = newSource === 'custom' ? (customTools.value[0]?.id ?? null) : null
  const first =
    newSource === 'custom'
      ? (customTools.value[0]?.name ?? '')
      : (toolOptions.value[0] ?? 'calculator')
  tool.toolName = first
  tool.toolConfig = {}
}

/** M5 自定义工具选择：记录 definitionId 并按名称回填（custom 工具 config 为空对象） */
function onCustomToolChange(tool: AgentTool, newName: string): void {
  if (newName === tool.toolName) return
  tool.toolName = newName
  tool.toolConfig = {}
  const def = customTools.value.find((c) => c.name === newName)
  tool.toolDefinitionId = def?.id ?? null
}

function addTool(): void {
  const first = toolOptions.value[0] ?? 'calculator'
  const defaults: Record<string, unknown> = {}
  for (const param of configParamOf(first)) {
    defaults[param] = ''
  }
  tools.value.push({ toolName: first, toolSource: 'builtin', toolConfig: defaults, enabled: true })
}

function removeTool(index: number): void {
  tools.value.splice(index, 1)
}

async function loadDetail(): Promise<void> {
  if (!isEdit.value) return
  loading.value = true
  try {
    const detail = await apiAgentDetail(agentId.value)
    name.value = detail.name
    description.value = detail.description ?? ''
    systemPrompt.value = detail.systemPrompt
    modelName.value = detail.modelName
    providerId.value = detail.providerId ?? null
    temperature.value = Number(detail.temperature)
    mode.value = detail.mode === 'workflow' ? 'workflow' : 'chat'
    visibility.value = detail.visibility === 'PUBLIC' ? 'PUBLIC' : 'PRIVATE'
    workflowId.value = detail.workflowId ?? null
    tools.value = detail.tools.length ? detail.tools : []
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  // 加载工具元数据（失败不阻断：退回内置工具列表）
  try {
    toolMeta.value = await apiToolsMeta()
  } catch {
    /* 元数据不可用时退回内置列表 */
  }
  // 加载本人工作流（工作流模式选择器；失败不阻断）
  try {
    const result = await apiWorkflowPage({ page: 1, size: 100 })
    workflows.value = result.list
  } catch {
    /* 工作流列表不可用时不展示选择器 */
  }
  // 加载模型 Provider（M4：provider 下拉 + 模型联动；失败不阻断）
  try {
    providers.value = (await apiProviderList()).filter((p) => p.enabled)
    if (providers.value.length && !providers.value.some((p) => p.id === providerId.value)) {
      providerId.value = null
    }
  } catch {
    /* Provider 列表不可用时回落默认模型 */
  }
  // M5 加载我的自定义工具（Agent 绑定选择器；失败不阻断）
  try {
    const result = await apiToolDefinitionPage({ page: 1, size: 100 })
    customTools.value = result.list
  } catch {
    /* 自定义工具不可用时不展示选择器 */
  }
  await loadDetail()
})

async function onSubmit(): Promise<void> {
  if (!name.value.trim()) {
    notifyError('请输入智能体名称')
    return
  }
  if (!systemPrompt.value.trim()) {
    notifyError('请输入系统提示词')
    return
  }
  const payload: AgentPayload = {
    name: name.value.trim(),
    description: description.value.trim() || undefined,
    systemPrompt: systemPrompt.value,
    modelName: modelName.value || 'qwen3.7-plus',
    providerId: providerId.value,
    temperature: Number(temperature.value) || 0.7,
    tools: tools.value.map((t) => ({
      toolName: t.toolName,
      toolSource: t.toolSource ?? 'builtin',
      toolDefinitionId: t.toolSource === 'custom' ? (t.toolDefinitionId ?? null) : null,
      toolConfig: t.toolConfig || {},
      enabled: t.enabled !== false,
    })),
    mode: mode.value,
    visibility: visibility.value,
    workflowId: workflowId.value,
  }
  saving.value = true
  try {
    if (isEdit.value) {
      await agentStore.update(agentId.value, payload)
      notifySuccess('保存成功')
    } else {
      const created = await agentStore.create(payload)
      notifySuccess('创建成功')
      router.replace(`/agents/${created.id}/edit`)
    }
  } catch (e) {
    notifyError((e as Error).message)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <AppLayout>
    <div class="page-container">
      <div class="page-header">
        <div>
          <div class="eyebrow">{{ isEdit ? `AGENT #${agentId}` : 'AGENT · NEW' }}</div>
          <h2>{{ isEdit ? '编辑智能体' : '新建智能体' }}</h2>
        </div>
        <button class="btn btn-secondary" @click="router.back()">返回</button>
      </div>

      <div v-if="loading" class="muted">加载中…</div>
      <div v-else class="card form">
        <div class="section-label">
          <span class="section-key">SPEC</span>基础规格
        </div>

        <div class="form-item">
          <label>名称 *</label>
          <input v-model="name" class="input" placeholder="如：Java Expert" maxlength="100" />
        </div>

        <div class="form-item">
          <label>描述</label>
          <input v-model="description" class="input" placeholder="一句话描述这个智能体" maxlength="500" />
        </div>

        <div class="form-row">
          <div class="form-item">
            <label>模型 Provider</label>
            <select v-model="providerId" class="select">
              <option :value="null">内置千问云端（默认）</option>
              <option v-for="p in providers" :key="p.id" :value="p.id">
                {{ p.name }}（{{ p.providerType }}）
              </option>
            </select>
          </div>
          <div class="form-item">
            <label>模型名称</label>
            <input
              v-if="!providerModels.length"
              v-model="modelName"
              class="input mono"
              placeholder="qwen3.7-plus"
            />
            <select v-else v-model="modelName" class="select">
              <option v-for="m in providerModels" :key="m" :value="m">{{ m }}</option>
            </select>
          </div>
          <div class="form-item">
            <label>温度（0-1）</label>
            <input v-model.number="temperature" class="input mono" type="number" step="0.05" min="0" max="1" />
          </div>
        </div>

        <div class="section-label">
          <span class="section-key">PROMPT</span>角色设定
        </div>

        <div class="form-item">
          <label>系统提示词 *</label>
          <textarea
            v-model="systemPrompt"
            class="textarea"
            rows="5"
            placeholder="定义智能体的角色与行为，如：你是一名资深Java工程师，帮助用户解决Java问题。"
          />
        </div>

        <div class="section-label">
          <span class="section-key">MODE</span>运行方式
        </div>

        <div class="form-item">
          <div class="mode-row">
            <label class="mode-option">
              <input v-model="mode" type="radio" value="chat" />
              对话模式 <span class="muted">— LLM 自主决策工具（ReAct 循环）</span>
            </label>
            <label class="mode-option">
              <input v-model="mode" type="radio" value="workflow" />
              工作流模式 <span class="muted">— 聊天消息作为 {message} 运行绑定的流程</span>
            </label>
          </div>
          <div v-if="mode === 'workflow'" class="form-item">
            <label>绑定工作流 *</label>
            <select v-model="workflowId" class="select workflow-select">
              <option v-for="wf in workflows" :key="wf.id" :value="wf.id">
                {{ wf.name }}（{{ wf.nodes.length }} 节点）
              </option>
            </select>
            <p v-if="!workflows.length" class="muted small-tip">
              暂无工作流，请先到「工作流」页面创建
            </p>
          </div>
        </div>

        <div class="section-label">
          <span class="section-key">SHARE</span>可见性
        </div>

        <div class="form-item">
          <div class="mode-row">
            <label class="mode-option">
              <input v-model="visibility" type="radio" value="PRIVATE" />
              私有 <span class="muted">— 仅创建者可见可用</span>
            </label>
            <label class="mode-option">
              <input v-model="visibility" type="radio" value="PUBLIC" />
              公开 <span class="muted">— 所有登录用户可见并可使用</span>
            </label>
          </div>
        </div>

        <div class="section-label">
          <span class="section-key">TOOLS</span>工具配置
          <span class="section-hint">内置工具 + 我的自定义工具；LLM 依据 Schema 自主调用；工作流模式下忽略</span>
        </div>

        <div class="form-item">
          <div v-for="(tool, index) in tools" :key="index" class="tool-card">
            <div class="tool-row">
              <select
                class="select tool-source"
                :value="tool.toolSource ?? 'builtin'"
                @change="onToolSourceChange(tool, ($event.target as HTMLSelectElement).value as 'builtin' | 'custom')"
              >
                <option value="builtin">内置工具</option>
                <option value="custom">我的自定义</option>
              </select>
              <select
                v-if="(tool.toolSource ?? 'builtin') === 'custom'"
                class="select tool-name"
                :value="tool.toolName"
                @change="onCustomToolChange(tool, ($event.target as HTMLSelectElement).value)"
              >
                <option v-for="ct in customTools" :key="ct.id" :value="ct.name">
                  {{ ct.displayName }}（{{ ct.name }}）
                </option>
              </select>
              <select
                v-else
                class="select tool-name"
                :value="tool.toolName"
                @change="onToolChange(tool, ($event.target as HTMLSelectElement).value)"
              >
                <option v-for="opt in toolOptions" :key="opt" :value="opt">{{ opt }}</option>
              </select>
              <span
                v-if="(tool.toolSource ?? 'builtin') === 'custom'"
                class="tool-desc muted"
              >
                {{ customToolMeta(tool.toolName)?.description || '自定义工具（定义见工具库）' }}
              </span>
              <span v-else-if="metaOf(tool.toolName)?.description" class="tool-desc muted">
                {{ metaOf(tool.toolName)?.description }}
              </span>
              <label class="tool-enabled">
                <input v-model="tool.enabled" type="checkbox" />
                启用
              </label>
              <button class="btn btn-danger btn-sm" @click="removeTool(index)">移除</button>
            </div>
            <div
              v-if="(tool.toolSource ?? 'builtin') === 'builtin' && configParamOf(tool.toolName).length"
              class="tool-config"
            >
              <div v-for="param in configParamOf(tool.toolName)" :key="param" class="form-item">
                <label class="tool-config-label">
                  {{ param }}
                  <span v-if="metaOf(tool.toolName)?.config[param]?.description" class="muted">
                    — {{ metaOf(tool.toolName)?.config[param]?.description }}
                  </span>
                </label>
                <input
                  v-model="(tool.toolConfig[param] as string)"
                  class="input"
                  :type="/key|token/i.test(param) ? 'password' : 'text'"
                  :placeholder="metaOf(tool.toolName)?.config[param]?.description"
                />
              </div>
            </div>
            <p
              v-if="(tool.toolSource ?? 'builtin') === 'custom' && !customTools.length"
              class="muted small-tip"
            >
              暂无自定义工具，请先到「工具库」创建
            </p>
          </div>
          <button class="btn btn-secondary btn-sm" @click="addTool">+ 添加工具</button>
        </div>

        <div class="form-actions">
          <button class="btn" :disabled="saving" @click="onSubmit">
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
.form {
  max-width: 760px;
}

.workflow-select {
  max-width: 420px;
}

.tool-card {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 10px 12px;
  margin-bottom: 8px;
}

.tool-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.tool-name {
  width: 160px;
}

.tool-source {
  width: 120px;
}

.tool-desc {
  flex: 1;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-enabled {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  white-space: nowrap;
}

.tool-config {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--line);
}

.tool-config .form-item {
  margin-bottom: 8px;
}

.tool-config-label {
  font-size: 13px;
}
</style>
