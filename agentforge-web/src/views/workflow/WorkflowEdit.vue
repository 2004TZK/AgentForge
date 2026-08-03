<script setup lang="ts">
/**
 * 工作流编辑/运行页（M3 Workflow v1）：
 * 节点编辑器（线性链）+ 只读流程图谱 + 触发运行 + 节点级日志 + 运行记录。
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import {
  apiCreateWorkflow,
  apiRunWorkflow,
  apiUpdateWorkflow,
  apiWorkflowDetail,
  apiWorkflowRuns,
} from '../../api/workflow'
import { notifyError, notifySuccess } from '../../utils/notify'
import type { WorkflowNode, WorkflowRun } from '../../types/workflow'

const route = useRoute()
const router = useRouter()

const isEdit = computed(() => route.params.id !== undefined)
const workflowId = computed(() => Number(route.params.id))

const name = ref('')
const description = ref('')
const nodes = ref<WorkflowNode[]>([])
const loading = ref(false)
const saving = ref(false)

const runInput = ref('{"message": "生成一份仓库报告"}')
const running = ref(false)
const lastRun = ref<WorkflowRun | null>(null)
const runs = ref<WorkflowRun[]>([])

/** 只读图谱：节点链（含结束标记） */
const graphNodes = computed(() => {
  const result: { key: string; type: string }[] = nodes.value.map((n) => ({
    key: n.nodeKey,
    type: n.nodeType,
  }))
  if (nodes.value.length && nodes.value[nodes.value.length - 1].nextNode === null) {
    result.push({ key: 'END', type: 'end' })
  }
  return result
})

const nextOptions = computed(() => [...nodes.value.map((n) => n.nodeKey), ''])
const nextLabel = (value: string | null): string => (value === null ? '结束' : value)

function addNode(): void {
  nodes.value.push({
    nodeKey: `node_${nodes.value.length + 1}`,
    nodeType: 'tool',
    params: defaultParams('tool'),
    nextNode: null,
  })
  fixNextLinks()
}

function removeNode(index: number): void {
  nodes.value.splice(index, 1)
  fixNextLinks()
}

/** 移除指向已删除节点的 next 引用 */
function fixNextLinks(): void {
  const keys = new Set(nodes.value.map((n) => n.nodeKey))
  for (const node of nodes.value) {
    if (node.nextNode !== null && !keys.has(node.nextNode)) {
      node.nextNode = null
    }
  }
}

function defaultParams(type: 'llm' | 'tool'): Record<string, unknown> {
  return type === 'llm'
    ? { prompt: '根据输入生成报告：{message}' }
    : { tool: 'calculator', payload: { expression: '{message}' } }
}

/** 节点类型切换：替换默认参数骨架（保留原参数中可复用的值） */
function onTypeChange(node: WorkflowNode): void {
  const defaults = defaultParams(node.nodeType)
  for (const key of Object.keys(defaults)) {
    if (!(key in node.params)) node.params[key] = defaults[key]
  }
  if (node.nodeType === 'tool' && !node.params.tool) node.params.tool = 'calculator'
}

/** 解析节点参数 JSON 文本（非法 JSON 抛错提示） */
function parseParamsText(text: string): Record<string, unknown> {
  if (!text.trim()) return {}
  return JSON.parse(text) as Record<string, unknown>
}

function paramsText(node: WorkflowNode): string {
  return JSON.stringify(node.params, null, 1)
}

function updateParams(node: WorkflowNode, text: string): void {
  try {
    node.params = parseParamsText(text)
  } catch {
    /* 编辑中暂不校验，提交时统一校验 */
  }
}

function validateNodes(): string | null {
  const keys = nodes.value.map((n) => n.nodeKey)
  if (!keys.length) return '至少需要一个节点'
  if (new Set(keys).size !== keys.length) return '节点键不能重复'
  for (const n of nodes.value) {
    if (!n.nodeKey.trim()) return '节点键不能为空'
    if (n.nextNode !== null && !keys.includes(n.nextNode)) {
      return `节点「${n.nodeKey}」的下一节点不存在: ${n.nextNode}`
    }
  }
  return null
}

async function onSubmit(): Promise<void> {
  if (!name.value.trim()) {
    notifyError('请输入工作流名称')
    return
  }
  const err = validateNodes()
  if (err) {
    notifyError(err)
    return
  }
  saving.value = true
  const payload = {
    name: name.value.trim(),
    description: description.value.trim() || undefined,
    nodes: nodes.value.map((n) => ({
      nodeKey: n.nodeKey.trim(),
      nodeType: n.nodeType,
      params: n.params,
      nextNode: n.nextNode,
    })),
  }
  try {
    if (isEdit.value) {
      await apiUpdateWorkflow(workflowId.value, payload)
      notifySuccess('保存成功')
    } else {
      const created = await apiCreateWorkflow(payload)
      notifySuccess('创建成功')
      router.replace(`/workflows/${created.id}/edit`)
    }
  } catch (e) {
    notifyError((e as Error).message)
  } finally {
    saving.value = false
  }
}

async function onRun(): Promise<void> {
  if (running.value) return
  let input: Record<string, unknown>
  try {
    input = JSON.parse(runInput.value || '{}') as Record<string, unknown>
  } catch {
    notifyError('运行输入不是合法 JSON')
    return
  }
  running.value = true
  try {
    lastRun.value = await apiRunWorkflow(workflowId.value, input)
    if (lastRun.value.status === 'SUCCESS') {
      notifySuccess('运行成功')
    } else {
      notifyError(`运行失败：${lastRun.value.error || '未知原因'}`)
    }
    loadRuns()
  } catch (e) {
    notifyError((e as Error).message)
  } finally {
    running.value = false
  }
}

async function loadRuns(): Promise<void> {
  try {
    const result = await apiWorkflowRuns(workflowId.value, { page: 1, size: 5 })
    runs.value = result.list
    if (!lastRun.value && result.list.length) {
      lastRun.value = result.list[0]
    }
  } catch {
    /* 运行记录加载失败不阻断 */
  }
}

async function loadDetail(): Promise<void> {
  if (!isEdit.value) return
  loading.value = true
  try {
    const detail = await apiWorkflowDetail(workflowId.value)
    name.value = detail.name
    description.value = detail.description ?? ''
    nodes.value = detail.nodes
    await loadRuns()
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (!isEdit.value) addNode()
  loadDetail()
})
</script>

<template>
  <AppLayout>
    <div class="page-container">
      <div class="page-header">
        <h2>{{ isEdit ? '编辑工作流' : '新建工作流' }}</h2>
        <button class="btn btn-secondary" @click="router.back()">返回</button>
      </div>

      <div v-if="loading" class="muted">加载中…</div>
      <div v-else class="card form">
        <div class="form-row">
          <div class="form-item">
            <label>名称 *</label>
            <input v-model="name" class="input" placeholder="如：仓库指标报告" maxlength="100" />
          </div>
          <div class="form-item">
            <label>描述</label>
            <input v-model="description" class="input" placeholder="流程用途说明" maxlength="500" />
          </div>
        </div>

        <div class="form-item">
          <label>只读图谱</label>
          <div v-if="graphNodes.length" class="graph">
            <template v-for="(node, idx) in graphNodes" :key="idx">
              <div class="graph-node" :class="node.type">
                <div class="graph-key">{{ node.key }}</div>
                <div class="graph-type">{{ node.type }}</div>
              </div>
              <span v-if="idx < graphNodes.length - 1" class="graph-arrow">→</span>
            </template>
          </div>
        </div>

        <div class="form-item">
          <label>节点定义（线性链，LLM 依据提示词 / 工具依据 Schema 执行）</label>
          <div v-for="(node, index) in nodes" :key="index" class="node-card">
            <div class="node-row">
              <input
                v-model="node.nodeKey"
                class="input node-key"
                placeholder="节点键（如 fetch_repo）"
                maxlength="100"
              />
              <select v-model="node.nodeType" class="select node-type" @change="onTypeChange(node)">
                <option value="tool">tool 工具</option>
                <option value="llm">llm 生成</option>
              </select>
              <select v-model="node.nextNode" class="select node-next">
                <option v-for="opt in nextOptions" :key="opt" :value="opt || null">
                  下一节点：{{ nextLabel((opt as string) || null) }}
                </option>
              </select>
              <button class="btn btn-danger btn-sm" @click="removeNode(index)">移除</button>
            </div>
            <div class="node-params">
              <label class="muted params-hint">节点参数（JSON，支持 {var} 模板；{message} 为对话触发时的用户消息）</label>
              <textarea
                class="textarea params-textarea"
                rows="3"
                :value="paramsText(node)"
                @input="updateParams(node, ($event.target as HTMLTextAreaElement).value)"
              />
            </div>
          </div>
          <button class="btn btn-secondary btn-sm" @click="addNode">+ 添加节点</button>
        </div>

        <div class="form-actions">
          <button class="btn" :disabled="saving" @click="onSubmit">
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </div>

        <template v-if="isEdit">
          <div class="run-section">
            <h3>运行测试</h3>
            <div class="form-item">
              <label>运行输入（JSON，模板变量；对话触发时自动注入 message）</label>
              <textarea v-model="runInput" class="textarea" rows="2" />
            </div>
            <button class="btn" :disabled="running" @click="onRun">
              {{ running ? '运行中…' : '▶ 运行' }}
            </button>

            <div v-if="lastRun" class="run-result">
              <div class="run-header">
                <span class="badge" :class="lastRun.status === 'SUCCESS' ? 'badge-ok' : 'badge-fail'">
                  {{ lastRun.status }}
                </span>
                <span class="muted">#{{ lastRun.id }} · {{ lastRun.startedTime }}</span>
              </div>
              <div v-if="lastRun.output" class="run-output">{{ lastRun.output }}</div>
              <div v-if="lastRun.error" class="run-error">{{ lastRun.error }}</div>
              <table v-if="lastRun.nodeLogs.length" class="table node-log-table">
                <thead>
                  <tr>
                    <th>节点</th>
                    <th>类型</th>
                    <th>状态</th>
                    <th>耗时</th>
                    <th>输出 / 错误</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="log in lastRun.nodeLogs" :key="log.node">
                    <td>{{ log.node }}</td>
                    <td>{{ log.type }}</td>
                    <td>
                      <span class="badge" :class="log.status === 'SUCCESS' ? 'badge-ok' : 'badge-fail'">
                        {{ log.status }}
                      </span>
                    </td>
                    <td>{{ log.durationMs }}ms</td>
                    <td class="log-cell">
                      <span v-if="log.output" class="log-text">{{ log.output }}</span>
                      <span v-if="log.error" class="log-error">{{ log.error }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div v-if="runs.length" class="runs-history">
              <h3>运行记录</h3>
              <div v-for="run in runs" :key="run.id" class="run-row">
                <button class="btn btn-secondary btn-sm" @click="lastRun = run">查看</button>
                <span class="badge" :class="run.status === 'SUCCESS' ? 'badge-ok' : 'badge-fail'">
                  {{ run.status }}
                </span>
                <span class="muted">#{{ run.id }} · {{ run.startedTime }} · 输入 {{ JSON.stringify(run.input) }}</span>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped src="./WorkflowEdit.style.css"></style>
