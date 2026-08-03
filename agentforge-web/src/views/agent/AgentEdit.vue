<script setup lang="ts">
/** 新建/编辑智能体：基础信息 + 工具配置（工具列表为简单 JSON 配置编辑） */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import { apiAgentDetail } from '../../api/agent'
import { useAgentStore } from '../../stores/agent'
import { notifyError, notifySuccess } from '../../utils/notify'
import type { AgentPayload, AgentTool } from '../../types/agent'

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
const loading = ref(false)
const saving = ref(false)

const TOOL_OPTIONS = ['calculator', 'github']

function addTool(): void {
  tools.value.push({ toolName: 'calculator', toolConfig: {}, enabled: true })
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

onMounted(loadDetail)
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
          <label>工具配置（Phase 4 启用工具调用）</label>
          <div v-for="(tool, index) in tools" :key="index" class="tool-row">
            <select v-model="tool.toolName" class="select tool-name">
              <option v-for="opt in TOOL_OPTIONS" :key="opt" :value="opt">{{ opt }}</option>
            </select>
            <label class="tool-enabled">
              <input v-model="tool.enabled" type="checkbox" />
              启用
            </label>
            <button class="btn btn-danger btn-sm" @click="removeTool(index)">移除</button>
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

.tool-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.tool-name {
  width: 160px;
}

.tool-enabled {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
}

.form-actions {
  margin-top: 8px;
}
</style>
