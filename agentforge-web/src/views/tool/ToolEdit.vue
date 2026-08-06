<script setup lang="ts">
/** 自定义工具编辑器：基本信息 + 参数 Schema 行式编辑 + HTTP/代码定义 + 示例参数测试 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import {
  apiCreateToolDefinition,
  apiTestToolDefinition,
  apiToolDefinitionDetail,
  apiUpdateToolDefinition,
} from '../../api/toolDefinition'
import { notifyError, notifySuccess } from '../../utils/notify'
import type { ParamRow, ToolDefinition, ToolTestResult } from '../../types/toolDefinition'

const route = useRoute()
const router = useRouter()

const isEdit = computed(() => route.params.id !== undefined)
const id = computed(() => Number(route.params.id))

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)

// ---- 基本信息 ----
const toolType = ref<'http' | 'script'>('http')
const name = ref('')
const displayName = ref('')
const description = ref('')
const visibility = ref<'PRIVATE' | 'PUBLIC'>('PRIVATE')

// ---- 参数 Schema 行式编辑 ----
const paramRows = ref<ParamRow[]>([{ key: '', type: 'string', description: '', required: true }])

// ---- HTTP 定义 ----
const method = ref<'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE' | 'HEAD' | 'OPTIONS'>('GET')
const url = ref('')
const headers = ref<{ key: string; value: string }[]>([
  { key: 'Content-Type', value: 'application/json' },
])
const query = ref<{ key: string; value: string }[]>([])
const bodyTemplateText = ref('{}')
const authType = ref<'none' | 'api_key' | 'bearer' | 'basic'>('none')
const authHeaderName = ref('X-API-Key')
const authValue = ref('')
const timeoutSeconds = ref(15)

// ---- 代码定义 ----
const scriptLanguage = ref<'python' | 'javascript'>('python')
const source = ref('')

// ---- 测试 ----
const testArgsText = ref('{\n  \n}')
const testResult = ref<ToolTestResult | null>(null)

function addParamRow(): void {
  paramRows.value.push({ key: '', type: 'string', description: '', required: true })
}

function removeParamRow(index: number): void {
  paramRows.value.splice(index, 1)
}

function addKv(rows: { key: string; value: string }[]): void {
  rows.push({ key: '', value: '' })
}

function removeKv(rows: { key: string; value: string }[], index: number): void {
  rows.splice(index, 1)
}

/** 参数行 → OpenAI function parameters */
function buildParameters(): Record<string, unknown> {
  const properties: Record<string, unknown> = {}
  const required: string[] = []
  for (const row of paramRows.value) {
    if (!row.key.trim()) continue
    const spec: Record<string, unknown> = { type: row.type }
    if (row.description) spec.description = row.description
    properties[row.key.trim()] = spec
    if (row.required) required.push(row.key.trim())
  }
  const parameters: Record<string, unknown> = { type: 'object', properties }
  if (required.length) parameters.required = required
  return parameters
}

function buildHttpConfig(): Record<string, unknown> | null {
  const headerMap: Record<string, string> = {}
  for (const h of headers.value) {
    if (h.key.trim()) headerMap[h.key.trim()] = h.value
  }
  const queryMap: Record<string, string> = {}
  for (const q of query.value) {
    if (q.key.trim()) queryMap[q.key.trim()] = q.value
  }
  const config: Record<string, unknown> = {
    method: method.value,
    url: url.value.trim(),
  }
  if (Object.keys(headerMap).length) config.headers = headerMap
  if (Object.keys(queryMap).length) config.query = queryMap
  const bodyText = bodyTemplateText.value.trim()
  if (bodyText && bodyText !== '{}') {
    try {
      config.bodyTemplate = JSON.parse(bodyText)
    } catch {
      config.bodyTemplate = bodyText // 非 JSON：按字符串模板发送
    }
  }
  if (authType.value !== 'none') {
    const auth: Record<string, unknown> = { type: authType.value }
    if (authHeaderName.value.trim()) auth.headerName = authHeaderName.value.trim()
    if (authValue.value && authValue.value !== '********') auth.value = authValue.value
    config.auth = auth
  }
  config.timeoutSeconds = timeoutSeconds.value
  return config
}

function buildScriptConfig(): Record<string, unknown> {
  return { language: scriptLanguage.value, source: source.value, entrypoint: 'run' }
}

function buildPayload() {
  return {
    name: name.value.trim(),
    displayName: displayName.value.trim(),
    description: description.value.trim() || undefined,
    toolType: toolType.value,
    parameters: buildParameters(),
    httpConfig: toolType.value === 'http' ? buildHttpConfig() : null,
    scriptConfig: toolType.value === 'script' ? buildScriptConfig() : null,
    visibility: visibility.value,
  }
}

function buildTestPayload() {
  return {
    toolType: toolType.value,
    httpConfig: toolType.value === 'http' ? buildHttpConfig() : null,
    scriptConfig: toolType.value === 'script' ? buildScriptConfig() : null,
    parameters: buildParameters(),
    args: JSON.parse(testArgsText.value || '{}') as Record<string, unknown>,
  }
}

/** 编辑回显：properties → 行 */
function fillParamRows(parameters: Record<string, unknown> | undefined): void {
  const properties = (parameters as { properties?: Record<string, unknown> })?.properties
  if (!properties) {
    paramRows.value = [{ key: '', type: 'string', description: '', required: true }]
    return
  }
  const required = new Set((parameters?.required as string[]) ?? [])
  paramRows.value = Object.entries(properties).map(([key, spec]) => ({
    key,
    type: (spec as { type?: string })?.type ?? 'string',
    description: (spec as { description?: string })?.description ?? '',
    required: required.has(key),
  }))
  if (!paramRows.value.length) {
    paramRows.value = [{ key: '', type: 'string', description: '', required: true }]
  }
}

/** 编辑回显：httpConfig → 表单 */
function fillHttpConfig(config: Record<string, unknown> | null | undefined): void {
  if (!config) return
  method.value = (config.method as typeof method.value) ?? 'GET'
  url.value = String(config.url ?? '')
  const h = config.headers as Record<string, string> | undefined
  headers.value = h
    ? Object.entries(h).map(([key, value]) => ({ key, value }))
    : [{ key: 'Content-Type', value: 'application/json' }]
  const q = config.query as Record<string, string> | undefined
  query.value = q ? Object.entries(q).map(([key, value]) => ({ key, value })) : []
  const body = config.bodyTemplate
  bodyTemplateText.value =
    body === undefined || body === null
      ? '{}'
      : typeof body === 'string'
        ? body
        : JSON.stringify(body, null, 2)
  const auth = config.auth as { type?: string; headerName?: string; value?: unknown } | undefined
  authType.value = (auth?.type as typeof authType.value) ?? 'none'
  if (auth) {
    authHeaderName.value = auth.headerName ?? 'Authorization'
    authValue.value = auth.value === undefined ? '' : String(auth.value)
  }
  timeoutSeconds.value = Number(config.timeoutSeconds ?? 15) || 15
}

async function loadDetail(): Promise<void> {
  if (!isEdit.value) return
  loading.value = true
  try {
    const detail: ToolDefinition = await apiToolDefinitionDetail(id.value)
    toolType.value = detail.toolType
    name.value = detail.name
    displayName.value = detail.displayName
    description.value = detail.description ?? ''
    visibility.value = detail.visibility
    fillParamRows(detail.parameters)
    if (detail.toolType === 'http') {
      fillHttpConfig(detail.httpConfig as unknown as Record<string, unknown>)
    } else {
      scriptLanguage.value = (detail.scriptConfig?.language as 'python' | 'javascript') ?? 'python'
      source.value = detail.scriptConfig?.source ?? ''
    }
  } catch (e) {
    notifyError((e as Error).message)
  } finally {
    loading.value = false
  }
}

onMounted(loadDetail)

async function onSubmit(): Promise<void> {
  if (!name.value.trim()) {
    notifyError('请输入工具名（小写字母开头，供 LLM 调用）')
    return
  }
  if (!/^[a-z][a-z0-9_]{1,49}$/.test(name.value.trim())) {
    notifyError('工具名须为小写字母开头，含小写字母/数字/下划线，长度 2-50')
    return
  }
  if (!displayName.value.trim()) {
    notifyError('请输入展示名称')
    return
  }
  if (toolType.value === 'http' && !url.value.trim()) {
    notifyError('请输入 HTTP URL')
    return
  }
  if (toolType.value === 'script' && !source.value.trim()) {
    notifyError('请输入代码')
    return
  }
  if (toolType.value === 'script' && source.value.length > 50 * 1024) {
    notifyError('代码大小不能超过 50KB')
    return
  }
  saving.value = true
  try {
    if (isEdit.value) {
      await apiUpdateToolDefinition(id.value, buildPayload())
      notifySuccess('保存成功')
    } else {
      const created = await apiCreateToolDefinition(buildPayload())
      notifySuccess('创建成功')
      router.replace(`/tools/${created.id}/edit`)
    }
  } catch (e) {
    notifyError((e as Error).message)
  } finally {
    saving.value = false
  }
}

async function onTest(): Promise<void> {
  let args: Record<string, unknown>
  try {
    args = JSON.parse(testArgsText.value || '{}') as Record<string, unknown>
  } catch {
    notifyError('示例参数不是合法 JSON')
    return
  }
  if (toolType.value === 'http' && !url.value.trim()) {
    notifyError('请输入 HTTP URL 后再测试')
    return
  }
  if (toolType.value === 'script' && !source.value.trim()) {
    notifyError('请输入代码后再测试')
    return
  }
  testResult.value = null
  testing.value = true
  try {
    testResult.value = await apiTestToolDefinition({
      toolType: toolType.value,
      httpConfig: toolType.value === 'http' ? buildHttpConfig() : null,
      scriptConfig: toolType.value === 'script' ? buildScriptConfig() : null,
      parameters: buildParameters(),
      args,
    })
  } catch (e) {
    notifyError((e as Error).message)
  } finally {
    testing.value = false
  }
}

/** 工具类型切换：重置测试结果 */
function onTypeChange(): void {
  testResult.value = null
  testArgsText.value = '{\n  \n}'
}
</script>

<template>
  <AppLayout>
    <div class="page-container">
      <div class="page-header">
        <div>
          <div class="eyebrow">{{ isEdit ? `TOOL #${id}` : 'TOOL · NEW' }}</div>
          <h2>{{ isEdit ? '编辑工具' : '新建工具' }}</h2>
        </div>
        <button class="btn btn-secondary" @click="router.back()">返回</button>
      </div>

      <div v-if="loading" class="muted">加载中…</div>
      <div v-else class="card form">
        <div class="section-label">
          <span class="section-key">SPEC</span>基本信息
        </div>

        <div class="form-item">
          <label>工具名 * <span class="muted">— 小写字母开头，供 LLM 调用（如 weather_query）</span></label>
          <input v-model="name" class="input mono" maxlength="50" placeholder="weather_query" />
        </div>
        <div class="form-row">
          <div class="form-item">
            <label>展示名称 *</label>
            <input v-model="displayName" class="input" maxlength="100" placeholder="天气查询" />
          </div>
          <div class="form-item">
            <label>可见性</label>
            <select v-model="visibility" class="select">
              <option value="PRIVATE">私有 — 仅我可看可绑定</option>
              <option value="PUBLIC">公开 — 所有人可见可绑定（密钥脱敏）</option>
            </select>
          </div>
        </div>
        <div class="form-item">
          <label>描述 <span class="muted">— 给 LLM 看的用途说明，越具体越容易被正确调用</span></label>
          <input v-model="description" class="input" maxlength="500" placeholder="查询指定城市当前天气" />
        </div>

        <div class="section-label">
          <span class="section-key">TYPE</span>工具形态
        </div>

        <div class="form-item">
          <div class="mode-row">
            <label class="mode-option">
              <input v-model="toolType" type="radio" value="http" @change="onTypeChange" />
              HTTP 工具 <span class="muted">— AI 服务按定义发起请求调用外部 API</span>
            </label>
            <label class="mode-option">
              <input v-model="toolType" type="radio" value="script" @change="onTypeChange" />
              代码工具 <span class="muted">— 代码在沙箱中受限执行（无外网）</span>
            </label>
          </div>
        </div>

        <div class="section-label">
          <span class="section-key">SCHEMA</span>调用参数（LLM 按此填充）
        </div>

        <div class="form-item">
          <div v-for="(row, index) in paramRows" :key="index" class="param-row">
            <input v-model="row.key" class="input mono param-key" placeholder="参数名" />
            <select v-model="row.type" class="select param-type">
              <option value="string">string</option>
              <option value="number">number</option>
              <option value="integer">integer</option>
              <option value="boolean">boolean</option>
              <option value="array">array</option>
              <option value="object">object</option>
            </select>
            <input v-model="row.description" class="input" placeholder="参数说明（可选）" />
            <label class="param-required">
              <input v-model="row.required" type="checkbox" />
              必填
            </label>
            <button class="btn btn-danger btn-sm" @click="removeParamRow(index)">×</button>
          </div>
          <button class="btn btn-secondary btn-sm" @click="addParamRow">+ 添加参数</button>
        </div>

        <!-- HTTP 定义 -->
        <template v-if="toolType === 'http'">
          <div class="section-label">
            <span class="section-key">HTTP</span>请求定义
          </div>
          <div class="form-row">
            <div class="form-item">
              <label>方法</label>
              <select v-model="method" class="select">
                <option v-for="m in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']" :key="m" :value="m">
                  {{ m }}
                </option>
              </select>
            </div>
            <div class="form-item url-item">
              <label>URL 模板 * <span class="muted">— 支持 {city} 占位符</span></label>
              <input v-model="url" class="input mono" placeholder="https://api.example.com/v1/weather?city={city}" />
            </div>
          </div>
          <div class="form-item">
            <label>Headers <span class="muted">— 值支持 {param} 占位符</span></label>
            <div v-for="(h, i) in headers" :key="i" class="param-row">
              <input v-model="h.key" class="input mono param-key" placeholder="Header 名" />
              <input v-model="h.value" class="input param-value" placeholder="值" />
              <button class="btn btn-danger btn-sm" @click="removeKv(headers, i)">×</button>
            </div>
            <button class="btn btn-secondary btn-sm" @click="addKv(headers)">+ 添加 Header</button>
          </div>
          <div class="form-item">
            <label>Query 参数 <span class="muted">— 值支持 {param} 占位符</span></label>
            <div v-for="(q, i) in query" :key="i" class="param-row">
              <input v-model="q.key" class="input mono param-key" placeholder="参数名" />
              <input v-model="q.value" class="input param-value" placeholder="值，如 {api_key}" />
              <button class="btn btn-danger btn-sm" @click="removeKv(query, i)">×</button>
            </div>
            <button class="btn btn-secondary btn-sm" @click="addKv(query)">+ 添加 Query</button>
          </div>
          <div class="form-item">
            <label>Body 模板 <span class="muted">— JSON 对象（支持 {param} 占位符）或纯字符串</span></label>
            <textarea v-model="bodyTemplateText" class="textarea mono" rows="4" />
          </div>
          <div class="form-item">
            <label>认证方式</label>
            <select v-model="authType" class="select auth-select">
              <option value="none">无</option>
              <option value="api_key">API Key（自定义请求头）</option>
              <option value="bearer">Bearer Token</option>
              <option value="basic">Basic Auth（用户名:密码）</option>
            </select>
          </div>
          <div v-if="authType !== 'none'" class="form-row">
            <div v-if="authType === 'api_key'" class="form-item">
              <label>请求头名称</label>
              <input v-model="authHeaderName" class="input mono" placeholder="X-API-Key" />
            </div>
            <div class="form-item auth-value-item">
              <label>
                密钥值
                <span class="muted">— {{ authValue === '********' ? '已加密保存，留空不修改' : '支持 {param} 占位符' }}</span>
              </label>
              <input
                v-model="authValue"
                class="input"
                type="password"
                :placeholder="authValue === '********' ? '（已保存，不修改请留空）' : 'sk-xxx 或 {api_key}'"
              />
            </div>
          </div>
          <div class="form-item">
            <label>超时（秒，1-60）</label>
            <input v-model.number="timeoutSeconds" class="input mono timeout-input" type="number" min="1" max="60" />
          </div>
        </template>

        <!-- 代码定义 -->
        <template v-else>
          <div class="section-label">
            <span class="section-key">CODE</span>代码定义
          </div>
          <div class="form-item">
            <label>语言</label>
            <select v-model="scriptLanguage" class="select">
              <option value="python">Python</option>
              <option value="javascript">JavaScript</option>
            </select>
          </div>
          <div class="form-item">
            <label>
              代码 *
              <span class="muted">
                — 定义 {{ scriptLanguage === 'python' ? 'def run(args: dict)' : 'export function run(args)' }}，
                返回 JSON 可序列化值；沙箱内无外网、非 root、资源受限（≤50KB）
              </span>
            </label>
            <textarea v-model="source" class="textarea mono code-area" rows="12" spellcheck="false" />
          </div>
        </template>

        <div class="section-label">
          <span class="section-key">TEST</span>测试执行
        </div>

        <div class="form-item">
          <label>示例参数（JSON）</label>
          <textarea v-model="testArgsText" class="textarea mono test-args" rows="3" spellcheck="false" />
          <div class="test-actions">
            <button class="btn btn-secondary btn-sm" :disabled="testing" @click="onTest">
              {{ testing ? '测试中…' : '▶ 运行测试' }}
            </button>
            <span class="muted small-tip">
              {{ toolType === 'http' ? '真实发起 HTTP 请求（SSRF 防护生效）' : '代码在沙箱中真实执行一次' }}
            </span>
          </div>
        </div>

        <div v-if="testResult" class="test-result" :class="testResult.ok ? 'test-ok' : 'test-fail'">
          <div class="test-result-head">
            <span class="badge" :class="testResult.ok ? 'badge-ok' : 'badge-danger'">
              {{ testResult.ok ? 'SUCCESS' : 'FAILED' }}
            </span>
            <span class="muted mono">耗时 {{ testResult.durationMs }}ms</span>
          </div>
          <pre v-if="testResult.ok" class="test-output mono">{{ formatResult(testResult.result) }}</pre>
          <pre v-else class="test-output mono">{{ testResult.error }}</pre>
          <pre v-if="testResult.stdout" class="test-output mono muted">{{ testResult.stdout }}</pre>
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

<script lang="ts">
/** 模板内展示结果格式化（避免把对象序列化为 [object Object]） */
function formatResult(result: unknown): string {
  if (typeof result === 'string') return result
  return JSON.stringify(result, null, 2)
}
</script>

<style scoped>
.form {
  max-width: 860px;
}

.url-item {
  flex: 1;
}

.param-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.param-key {
  width: 180px;
}

.param-type {
  width: 110px;
}

.param-value {
  flex: 1;
}

.param-required {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  white-space: nowrap;
}

.auth-select {
  width: 260px;
}

.auth-value-item {
  flex: 1;
}

.timeout-input {
  width: 120px;
}

.code-area {
  font-size: 13px;
  line-height: 1.6;
}

.test-args {
  font-size: 13px;
}

.test-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
}

.test-result {
  border-radius: var(--radius);
  padding: 10px 12px;
  margin-bottom: 12px;
}

.test-ok {
  border: 1px solid var(--ok, #2f9e6e);
  background: rgba(47, 158, 110, 0.08);
}

.test-fail {
  border: 1px solid #d6455b;
  background: rgba(214, 69, 91, 0.08);
}

.test-result-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.test-output {
  margin: 0;
  max-height: 260px;
  overflow: auto;
  font-size: 12.5px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
}

.badge-danger {
  background: rgba(214, 69, 91, 0.16);
  color: #ff7a8a;
}
</style>
