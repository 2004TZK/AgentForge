<script setup lang="ts">
/** 模型 Provider 管理页（M4 多模型配置）：列表 / 创建 / 编辑 / 删除 / 启用切换 */
import { onMounted, ref } from 'vue'
import AppLayout from '../../components/layout/AppLayout.vue'
import {
  apiCreateProvider,
  apiDeleteProvider,
  apiProviderList,
  apiUpdateProvider,
} from '../../api/provider'
import { notifyError, notifySuccess } from '../../utils/notify'
import type { Provider, ProviderPayload } from '../../types/provider'

const list = ref<Provider[]>([])
const loading = ref(false)

// 编辑态（null = 列表模式）
const editing = ref<Provider | null>(null)
/** 表单是否显示（新建/编辑共用；与 editing 解耦，修复列表非空时"新建"无反应） */
const showForm = ref(false)
const form = ref<ProviderPayload>({
  name: '',
  providerType: 'ollama',
  baseUrl: '',
  apiKey: '',
  models: [],
  enabled: true,
})
const modelsText = ref('')
const saving = ref(false)

async function load(): Promise<void> {
  loading.value = true
  try {
    list.value = await apiProviderList()
  } catch (e) {
    notifyError((e as Error).message)
  } finally {
    loading.value = false
  }
}

function startCreate(): void {
  editing.value = null
  showForm.value = true
  form.value = { name: '', providerType: 'ollama', baseUrl: '', apiKey: '', models: [], enabled: true }
  modelsText.value = ''
}

function startEdit(p: Provider): void {
  editing.value = p
  showForm.value = true
  form.value = {
    name: p.name,
    providerType: p.providerType,
    baseUrl: p.baseUrl,
    apiKey: p.apiKey ?? '',
    models: p.models,
    enabled: p.enabled,
  }
  modelsText.value = p.models.join(', ')
}

function cancelEdit(): void {
  editing.value = null
  showForm.value = false
}

async function onSubmit(): Promise<void> {
  if (!form.value.name.trim() || !form.value.baseUrl.trim()) {
    notifyError('名称与 Base URL 必填')
    return
  }
  const models = modelsText.value
    .split(/[,，]/)
    .map((m) => m.trim())
    .filter(Boolean)
  saving.value = true
  try {
    const payload: ProviderPayload = { ...form.value, models }
    if (editing.value) {
      await apiUpdateProvider(editing.value.id, payload)
      notifySuccess('保存成功')
    } else {
      await apiCreateProvider(payload)
      notifySuccess('创建成功')
    }
    editing.value = null
    showForm.value = false
    await load()
  } catch (e) {
    notifyError((e as Error).message)
  } finally {
    saving.value = false
  }
}

async function toggleEnabled(p: Provider): Promise<void> {
  try {
    await apiUpdateProvider(p.id, {
      name: p.name,
      providerType: p.providerType,
      baseUrl: p.baseUrl,
      apiKey: p.apiKey ?? '',
      models: p.models,
      enabled: !p.enabled,
    })
    await load()
  } catch (e) {
    notifyError((e as Error).message)
  }
}

async function onDelete(p: Provider): Promise<void> {
  if (!window.confirm(`确认删除 Provider「${p.name}」？`)) return
  try {
    await apiDeleteProvider(p.id)
    notifySuccess('删除成功')
    await load()
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
        <h2>模型 Provider</h2>
        <button class="btn" @click="startCreate">+ 新建 Provider</button>
      </div>

      <div v-if="loading" class="muted">加载中…</div>

      <div v-else-if="showForm || list.length === 0" class="card form provider-form">
        <h3>{{ editing ? '编辑 Provider' : '新建 Provider' }}</h3>
        <div class="form-row">
          <div class="form-item">
            <label>名称 *</label>
            <input v-model="form.name" class="input" placeholder="如：本地 Ollama / DeepSeek 云端" />
          </div>
          <div class="form-item">
            <label>类型</label>
            <select v-model="form.providerType" class="select">
              <option value="ollama">ollama（本地原生，think 可控）</option>
              <option value="openai">openai（OpenAI 兼容）</option>
            </select>
          </div>
        </div>
        <div class="form-row">
          <div class="form-item">
            <label>Base URL *</label>
            <input
              v-model="form.baseUrl"
              class="input"
              placeholder="http://ollama:11434 或 https://api.deepseek.com/v1"
            />
          </div>
          <div class="form-item">
            <label>API Key（本地模型留空）</label>
            <input v-model="form.apiKey" class="input" type="password" placeholder="留空保持不变；已配置 Key 不回显明文" />
          </div>
        </div>
        <div class="form-item">
          <label>可用模型（逗号分隔）</label>
          <input v-model="modelsText" class="input" placeholder="qwen3.5:0.8b, bge-m3" />
        </div>
        <div class="form-item">
          <label class="mode-option">
            <input v-model="form.enabled" type="checkbox" class="checkbox" />
            启用（可被智能体选择）
          </label>
        </div>
        <div class="form-actions">
          <button class="btn" :disabled="saving" @click="onSubmit">
            {{ saving ? '保存中…' : '保存' }}
          </button>
          <button class="btn btn-secondary" @click="cancelEdit">取消</button>
        </div>
      </div>

      <div v-else class="card">
        <table class="table">
          <thead>
            <tr>
              <th>名称</th>
              <th>类型</th>
              <th>Base URL</th>
              <th>模型</th>
              <th>状态</th>
              <th>来源</th>
              <th class="col-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in list" :key="p.id">
              <td><strong>{{ p.name }}</strong></td>
              <td>{{ p.providerType }}</td>
              <td class="muted ellipsis">{{ p.baseUrl }}</td>
              <td class="muted">{{ p.models.join(', ') || '-' }}</td>
              <td>
                <span class="badge" :class="p.enabled ? 'badge-ok' : 'badge-warn'">
                  {{ p.enabled ? '启用' : '停用' }}
                </span>
              </td>
              <td class="muted">{{ p.creatorId === 0 ? '系统内置' : '自定义' }}</td>
              <td class="col-actions">
                <button
                  v-if="p.creatorId !== 0"
                  class="btn btn-secondary btn-sm"
                  @click="startEdit(p)"
                >
                  编辑
                </button>
                <button
                  v-if="p.creatorId !== 0"
                  class="btn btn-secondary btn-sm"
                  @click="toggleEnabled(p)"
                >
                  {{ p.enabled ? '停用' : '启用' }}
                </button>
                <button
                  v-if="p.creatorId !== 0"
                  class="btn btn-danger btn-sm"
                  @click="onDelete(p)"
                >
                  删除
                </button>
                <span v-else class="muted">—</span>
              </td>
            </tr>
          </tbody>
        </table>
        <p class="muted small-tip">
          内置 Provider 由系统维护（本机 Ollama）；自定义 Provider 支持接入任意 OpenAI 兼容服务。
        </p>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
.provider-form {
  max-width: 760px;
}

.checkbox {
  margin-right: 8px;
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
  width: 220px;
}

.col-actions .btn {
  margin-right: 6px;
}

.ellipsis {
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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

.small-tip {
  padding-top: 10px;
  font-size: 13px;
}
</style>
