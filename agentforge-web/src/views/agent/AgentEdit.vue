<script setup lang="ts">
/** 新建/编辑智能体：基础信息 + 工具配置（M3 起按 Schema 渲染配置表单） */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { apiAgentDetail, apiToolsMeta } from '../../api/agent'
import { useAgentStore } from '../../stores/agent'
import { notifyError, notifySuccess } from '../../utils/notify'
import type { AgentPayload, AgentTool, ToolMeta } from '../../types/agent'

const route = useRoute()
const router = useRouter()
const agentStore = useAgentStore()

const isEdit = computed(() => route.params.id !== undefined)
const agentId = computed(() => Number(route.params.id))

const name = ref('')
const description = ref('')
const systemPrompt = ref('')
const modelName = ref('deepseek-chat')
const temperature = ref(0.7)
const tools = ref<AgentTool[]>([{ toolName: 'calculator', toolConfig: {}, enabled: true }])
const toolMeta = ref<ToolMeta[]>([])
const loading = ref(false)
const saving = ref(false)

/** 工具选项（M3：由 /tools/meta 动态加载；加载失败时退回内置列表） */
const toolOptions = computed(() =>
  toolMeta.value.length ? toolMeta.value.map((t) => t.name) : ['calculator', 'github'],
)

function metaOf(toolName: string): ToolMeta | undefined {
  return toolMeta.value.find((t) => t.name === toolName)
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

function addTool(): void {
  const first = toolOptions.value[0] ?? 'calculator'
  const defaults: Record<string, unknown> = {}
  for (const param of configParamOf(first)) {
    defaults[param] = ''
  }
  tools.value.push({ toolName: first, toolConfig: defaults, enabled: true })
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
    temperature.value = Number(detail.temperature)
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
    modelName: modelName.value || 'deepseek-chat',
    temperature: Number(temperature.value) || 0.7,
    tools: tools.value.map((t) => ({
      toolName: t.toolName,
      toolConfig: t.toolConfig || {},
      enabled: t.enabled !== false,
    })),
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
        <h2>{{ isEdit ? '编辑智能体' : '新建智能体' }}</h2>
        <button class="btn btn-secondary" @click="router.back()">返回</button>
      </div>

      <div v-if="loading" class="muted">加载中…</div>
      <div v-else class="card form">
        <div class="form-item">
          <label>名称 *</label>
          <input v-model="name" class="input" placeholder="如：Java Expert" maxlength="100" />
        </div>

        <div class="form-item">
          <label>描述</label>
          <input v-model="description" class="input" placeholder="一句话描述这个智能体" maxlength="500" />
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

        <div class="form-row">
          <div class="form-item">
            <label>模型</label>
            <input v-model="modelName" class="input" placeholder="deepseek-chat" />
          </div>
          <div class="form-item">
            <label>温度（0-1）</label>
            <input v-model.number="temperature" class="input" type="number" step="0.05" min="0" max="1" />
          </div>
        </div>

        <div class="form-item">
          <label>工具配置（M3：LLM 依据 Schema 自主调用）</label>
          <div v-for="(tool, index) in tools" :key="index" class="tool-card">
            <div class="tool-row">
              <select
                class="select tool-name"
                :value="tool.toolName"
                @change="onToolChange(tool, ($event.target as HTMLSelectElement).value)"
              >
                <option v-for="opt in toolOptions" :key="opt" :value="opt">{{ opt }}</option>
              </select>
              <span v-if="metaOf(tool.toolName)?.description" class="tool-desc muted">
                {{ metaOf(tool.toolName)?.description }}
              </span>
              <label class="tool-enabled">
                <input v-model="tool.enabled" type="checkbox" />
                启用
              </label>
              <button class="btn btn-danger btn-sm" @click="removeTool(index)">移除</button>
            </div>
            <div v-if="configParamOf(tool.toolName).length" class="tool-config">
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
  max-width: 720px;
}

.form-row {
  display: flex;
  gap: 16px;
}

.form-row .form-item {
  flex: 1;
}

.tool-card {
  border: 1px solid var(--color-border);
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
  border-top: 1px dashed var(--color-border);
}

.tool-config .form-item {
  margin-bottom: 8px;
}

.tool-config-label {
  font-size: 13px;
}

.form-actions {
  margin-top: 8px;
}
</style>
