<script setup lang="ts">
/**
 * 聊天页：选择智能体 → 会话列表（M2 多会话）→ 发送消息（SSE 流式打字机 + 失败重试）
 * 助手回答可展示知识库引用（来源文件列表，点击查看片段）。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import MarkdownView from '../../components/common/MarkdownView.vue'
import { useAgentStore } from '../../stores/agent'
import { useChatStore } from '../../stores/chat'
import { notifyError } from '../../utils/notify'

const route = useRoute()
const agentStore = useAgentStore()
const chatStore = useChatStore()

const agents = ref(agentStore.list)
const selectedAgentId = ref<number | null>(null)
const input = ref('')
const scrollRef = ref<HTMLElement | null>(null)
/** 已展开片段的引用（key: `${msgIndex}-${srcIndex}`） */
const expandedSources = ref<Set<string>>(new Set())

const sending = computed(() => chatStore.sending)

async function ensureAgents(): Promise<void> {
  if (!agents.value.length) {
    await agentStore.fetchList(1, 100)
    agents.value = agentStore.list
  }
}

/** 切换智能体：重置会话与消息，加载会话列表与当前会话历史 */
async function onAgentChange(agentIdValue: number): Promise<void> {
  chatStore.reset(agentIdValue)
  try {
    await chatStore.ensureSessions()
    if (chatStore.currentSessionId) {
      await chatStore.loadHistory(agentIdValue, chatStore.currentSessionId)
    }
  } catch {
    notifyError('会话加载失败')
  }
  scrollToBottom()
}

/** 切换会话：加载该会话历史 */
async function onSessionChange(sessionId: number): Promise<void> {
  if (chatStore.currentSessionId === sessionId) return
  chatStore.currentSessionId = sessionId
  try {
    await chatStore.loadHistory(chatStore.agentId!, sessionId)
  } catch {
    notifyError('历史记录加载失败')
  }
  scrollToBottom()
}

async function onCreateSession(): Promise<void> {
  try {
    await chatStore.createSession()
  } catch (e) {
    notifyError((e as Error).message)
  }
}

async function onDeleteSession(sessionId: number): Promise<void> {
  if (!window.confirm('确认删除该会话？会话内消息将不再展示（数据保留）。')) return
  try {
    await chatStore.deleteSession(sessionId)
  } catch (e) {
    notifyError((e as Error).message)
  }
}

function toggleSource(key: string): void {
  const next = new Set(expandedSources.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expandedSources.value = next
}

async function onSend(): Promise<void> {
  const content = input.value.trim()
  if (!content || sending.value) return
  if (!selectedAgentId.value) {
    notifyError('请先选择智能体')
    return
  }
  input.value = ''
  try {
    await chatStore.send(content)
  } catch (e) {
    notifyError((e as Error).message)
  }
}

function scrollToBottom(): void {
  requestAnimationFrame(() => {
    if (scrollRef.value) scrollRef.value.scrollTop = scrollRef.value.scrollHeight
  })
}

// 消息长度与内容变化均触发滚动（流式增量更新内容时持续跟随底部）
watch(
  () => {
    const last = chatStore.messages[chatStore.messages.length - 1]
    return last?.content
  },
  scrollToBottom,
)

onMounted(async () => {
  await ensureAgents()
  const routeAgentId = Number(route.params.agentId)
  if (routeAgentId) {
    selectedAgentId.value = routeAgentId
    await onAgentChange(routeAgentId)
  }
})
</script>

<template>
  <AppLayout>
    <div class="chat-page">
      <div class="chat-side">
        <h3 class="chat-side-title">选择智能体</h3>
        <div v-for="agent in agents" :key="agent.id" class="agent-item">
          <button
            class="agent-btn"
            :class="{ active: selectedAgentId === agent.id }"
            @click="selectedAgentId = agent.id; onAgentChange(agent.id)"
          >
            {{ agent.name }}
          </button>
        </div>
        <p v-if="!agents.length" class="muted">暂无智能体，请先到「智能体」页面创建</p>

        <template v-if="selectedAgentId">
          <div class="session-header">
            <h3 class="chat-side-title">会话</h3>
            <button class="btn btn-secondary btn-sm" @click="onCreateSession">＋新建</button>
          </div>
          <div
            v-for="session in chatStore.sessions"
            :key="session.id"
            class="agent-item"
          >
            <div class="session-row">
              <button
                class="agent-btn session-btn"
                :class="{ active: chatStore.currentSessionId === session.id }"
                @click="onSessionChange(session.id)"
              >
                {{ session.name }}
              </button>
              <button
                class="session-del"
                title="删除会话"
                @click.stop="onDeleteSession(session.id)"
              >
                ×
              </button>
            </div>
          </div>
          <p v-if="!chatStore.sessions.length" class="muted">暂无会话，点击「新建」开始对话</p>
        </template>
      </div>

      <div class="chat-main card">
        <div ref="scrollRef" class="messages">
          <div v-if="!chatStore.messages.length" class="muted empty-tip">
            {{ selectedAgentId ? '开始与智能体对话吧' : '请选择左侧的智能体开始对话' }}
          </div>
          <div
            v-for="(msg, index) in chatStore.messages"
            :key="index"
            class="message"
            :class="msg.role"
          >
            <div class="bubble" :class="{ 'bubble-error': msg.status === 'error' }">
              <MarkdownView v-if="msg.role === 'assistant'" :content="msg.content" />
              <template v-else>{{ msg.content }}</template>
              <span v-if="msg.status === 'streaming'" class="cursor">▍</span>
              <div v-if="msg.role === 'assistant' && msg.toolCalls?.length" class="tool-calls">
                <span class="tool-calls-label">🔧 工具：</span>
                <span v-for="(call, callIdx) in msg.toolCalls" :key="callIdx" class="tool-chip">
                  {{ call }}
                </span>
              </div>
              <div v-if="msg.role === 'assistant' && msg.sources?.length" class="sources">
                <span class="sources-label">来源：</span>
                <button
                  v-for="(src, srcIndex) in msg.sources"
                  :key="`${index}-${srcIndex}`"
                  class="source-chip"
                  @click="toggleSource(`${index}-${srcIndex}`)"
                >
                  {{ src.file }}
                </button>
                <div
                  v-if="expandedSources.has(`${index}-${srcIndex}`)"
                  :key="`snippet-${index}-${srcIndex}`"
                  class="source-snippet"
                >
                  {{ msg.sources![srcIndex].snippet }}
                </div>
              </div>
              <div v-if="msg.status === 'error'" class="error-line">
                <span class="error-text">{{ msg.error || '回答失败' }}</span>
                <button class="btn btn-secondary btn-sm" @click="chatStore.retry()">重试</button>
              </div>
            </div>
          </div>
        </div>

        <div class="composer">
          <textarea
            v-model="input"
            class="textarea input-box"
            rows="2"
            placeholder="输入消息，Enter 发送，Shift+Enter 换行"
            @keydown.enter.exact.prevent="onSend"
          />
          <button v-if="sending" class="btn btn-secondary" @click="chatStore.stop()">停止</button>
          <button class="btn" :disabled="sending" @click="onSend">
            {{ sending ? '思考中…' : '发送' }}
          </button>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
.chat-page {
  display: flex;
  height: 100%;
  padding: 0;
}

.chat-side {
  width: 220px;
  padding: 16px;
  border-right: 1px solid var(--color-border);
  overflow-y: auto;
  flex-shrink: 0;
}

.chat-side-title {
  margin: 0 0 12px;
  font-size: 14px;
  color: var(--color-text-secondary);
}

.session-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 18px;
}

.session-header .chat-side-title {
  margin: 0;
}

.agent-item {
  margin-bottom: 6px;
}

.agent-btn {
  width: 100%;
  text-align: left;
  padding: 9px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: var(--color-surface);
  cursor: pointer;
  font-size: 14px;
}

.agent-btn:hover {
  border-color: var(--color-primary);
}

.agent-btn.active {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}

.session-row {
  display: flex;
  align-items: center;
  gap: 4px;
}

.session-btn {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-del {
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 16px;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 4px;
}

.session-del:hover {
  color: var(--color-danger);
  background: rgba(239, 68, 68, 0.08);
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  margin: 16px;
  padding: 0;
  overflow: hidden;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.empty-tip {
  text-align: center;
  padding: 48px 0;
}

.message {
  display: flex;
  margin-bottom: 14px;
}

.message.user {
  justify-content: flex-end;
}

.message.assistant {
  justify-content: flex-start;
}

.bubble {
  max-width: 78%;
  padding: 10px 14px;
  border-radius: 10px;
  background: #f1f5f9;
  white-space: pre-wrap;
}

.message.user .bubble {
  background: var(--color-primary);
  color: #fff;
}

.bubble-error {
  border: 1px solid var(--color-danger);
}

/* 流式输入光标 */
.cursor {
  color: var(--color-primary);
  animation: blink 1s step-start infinite;
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}

.tool-calls {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.tool-calls-label {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.tool-chip {
  border: 1px dashed var(--color-primary);
  color: var(--color-primary);
  background: rgba(37, 99, 235, 0.04);
  border-radius: 6px;
  padding: 2px 8px;
  font-size: 12px;
  word-break: break-all;
}

.sources {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.sources-label {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.source-chip {
  border: 1px solid var(--color-primary);
  color: var(--color-primary);
  background: transparent;
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 12px;
  cursor: pointer;
}

.source-chip:hover {
  background: rgba(37, 99, 235, 0.08);
}

.source-snippet {
  width: 100%;
  margin-top: 6px;
  padding: 8px 10px;
  border-left: 3px solid var(--color-primary);
  background: rgba(37, 99, 235, 0.05);
  border-radius: 4px;
  font-size: 12px;
  color: var(--color-text);
  white-space: pre-wrap;
}

.error-line {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.error-text {
  font-size: 12px;
  color: var(--color-danger);
}

.composer {
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  border-top: 1px solid var(--color-border);
  align-items: flex-end;
}

.input-box {
  flex: 1;
}
</style>
