<script setup lang="ts">
/**
 * 聊天页：选择智能体 → 会话列表（M2 多会话）→ 发送消息（SSE 流式打字机 + 失败重试）
 * 助手回答可展示知识库引用（来源文件列表，点击查看片段）。
 * 设计签名：助手回答是「冷却的金属」——流式输出时左缘烧成锻火橙，完成后冷却回发丝线。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from '../../components/layout/AppLayout.vue'
import MarkdownView from '../../components/common/MarkdownView.vue'
import StarChartCard from '../../components/chat/StarChartCard.vue'
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

const selectedAgent = computed(() => agents.value.find((a) => a.id === selectedAgentId.value))

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
        <div class="eyebrow">AGENTS · {{ agents.length }}</div>
        <div v-for="agent in agents" :key="agent.id" class="agent-item">
          <button
            class="agent-btn"
            :class="{ active: selectedAgentId === agent.id }"
            @click="selectedAgentId = agent.id; onAgentChange(agent.id)"
          >
            {{ agent.name }}
          </button>
        </div>
        <p v-if="!agents.length" class="muted side-tip">
          暂无智能体，请先到「智能体」页面创建
        </p>

        <template v-if="selectedAgentId">
          <div class="session-header">
            <div class="eyebrow">SESSIONS · {{ chatStore.sessions.length }}</div>
            <button class="btn btn-secondary btn-sm" @click="onCreateSession">＋新建</button>
          </div>
          <div v-for="session in chatStore.sessions" :key="session.id" class="agent-item">
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
          <p v-if="!chatStore.sessions.length" class="muted side-tip">
            暂无会话，点击「新建」开始对话
          </p>
        </template>
      </div>

      <div class="chat-main card">
        <div class="chat-head">
          <div class="chat-head-name">{{ selectedAgent?.name ?? '未选择智能体' }}</div>
          <div v-if="selectedAgentId" class="eyebrow">
            AGENT #{{ selectedAgentId }}<template v-if="chatStore.currentSessionId">
              · SESSION #{{ chatStore.currentSessionId }}</template
            >
          </div>
        </div>

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
            <div
              class="bubble"
              :class="{ 'bubble-assistant': msg.role === 'assistant', 'bubble-streaming': msg.status === 'streaming', 'bubble-error': msg.status === 'error' }"
            >
              <MarkdownView v-if="msg.role === 'assistant'" :content="msg.content" />
              <template v-else>{{ msg.content }}</template>
              <span v-if="msg.status === 'streaming'" class="cursor">▍</span>
              <div v-if="msg.role === 'assistant' && msg.toolCalls?.length" class="tool-calls">
                <span class="tool-calls-label">工具：</span>
                <span v-for="(call, callIdx) in msg.toolCalls" :key="callIdx" class="tool-chip">
                  {{ call }}
                </span>
              </div>
              <StarChartCard v-if="msg.role === 'assistant' && msg.chart" :chart="msg.chart" />
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

/* ---- 左侧：零件架（智能体 / 会话） ---- */
.chat-side {
  width: 228px;
  padding: 18px 14px;
  border-right: 1px solid var(--line);
  background: rgba(255, 253, 247, 0.55);
  overflow-y: auto;
  flex-shrink: 0;
}

.chat-side .eyebrow {
  margin-bottom: 12px;
}

.side-tip {
  font-size: 12px;
  line-height: 1.7;
  margin: 8px 0;
}

.session-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 20px 0 12px;
}

.session-header .eyebrow {
  margin: 0;
}

.agent-item {
  margin-bottom: 6px;
}

.agent-btn {
  width: 100%;
  text-align: left;
  padding: 9px 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--card);
  color: var(--ink);
  cursor: pointer;
  font-size: 14px;
  font-family: inherit;
  transition: border-color 0.15s, background 0.15s, color 0.15s;
}

.agent-btn:hover {
  border-color: var(--forge);
}

/* 激活 = 烙上锻火标记 */
.agent-btn.active {
  background: var(--ink);
  color: var(--card);
  border-color: var(--ink);
  font-weight: 600;
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
  color: var(--steel);
  font-size: 16px;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 4px;
}

.session-del:hover {
  color: var(--rust);
  background: rgba(179, 38, 30, 0.08);
}

/* ---- 对话主体：锻台 ---- */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  margin: 16px;
  padding: 0;
  overflow: hidden;
}

.chat-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 13px 20px;
  border-bottom: 1px solid var(--line);
  flex-shrink: 0;
}

.chat-head-name {
  font-size: 15px;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
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
  white-space: pre-wrap;
  transition: border-color 0.6s ease, box-shadow 0.6s ease, background 0.6s ease;
}

/* 用户 = 墨黑的锻件 */
.message.user .bubble {
  background: var(--ink);
  color: var(--card);
}

/* 助手 = 冷却的金属：左缘余烬，完成后冷却回发丝线 */
.bubble-assistant {
  background: var(--card);
  border: 1px solid var(--line);
  border-left: 3px solid var(--line);
  color: var(--ink);
}

.bubble-streaming {
  border-left-color: var(--forge-glow);
  box-shadow: 0 0 16px -4px rgba(232, 89, 12, 0.35);
}

.bubble-error {
  border-color: var(--rust);
  border-left-color: var(--rust);
}

/* 用户气泡上的错误：墨黑底上红边框不可见，改为铁锈左缘 */
.message.user .bubble.bubble-error {
  border-left-color: var(--rust);
  box-shadow: 0 0 16px -6px rgba(179, 38, 30, 0.5);
}

/* 余烬光标 */
.cursor {
  color: var(--forge-glow);
  animation: ember 1s step-start infinite;
}

@keyframes ember {
  0%,
  100% {
    opacity: 1;
    text-shadow: 0 0 6px rgba(232, 89, 12, 0.55);
  }
  50% {
    opacity: 0.35;
    text-shadow: none;
  }
}

/* 工具调用 = 虚线钢印 */
.tool-calls {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.tool-calls-label {
  font-size: 12px;
  color: var(--steel);
}

.tool-chip {
  border: 1px dashed var(--forge);
  color: var(--forge);
  background: var(--forge-tint);
  border-radius: 6px;
  padding: 2px 8px;
  font-family: var(--font-mono);
  font-size: 11.5px;
  word-break: break-all;
}

/* 知识库引用 */
.sources {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.sources-label {
  font-size: 12px;
  color: var(--steel);
}

.source-chip {
  border: 1px solid var(--forge);
  color: var(--forge);
  background: transparent;
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 12px;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.15s;
}

.source-chip:hover {
  background: var(--forge-tint);
}

.source-snippet {
  width: 100%;
  margin-top: 6px;
  padding: 8px 10px;
  border-left: 3px solid var(--forge);
  background: rgba(181, 67, 0, 0.05);
  border-radius: 4px;
  font-size: 12px;
  color: var(--ink);
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
  color: var(--rust);
}

/* 输入台 */
.composer {
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  border-top: 1px solid var(--line);
  align-items: flex-end;
  background: rgba(255, 253, 247, 0.55);
}

.input-box {
  flex: 1;
  max-height: 160px;
}

@media (max-width: 860px) {
  .chat-side {
    width: 168px;
    padding: 14px 10px;
  }

  .chat-main {
    margin: 10px;
  }
}
</style>
