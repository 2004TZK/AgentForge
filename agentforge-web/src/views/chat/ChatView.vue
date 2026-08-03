<script setup lang="ts">
/** 聊天页：选择智能体 → 加载历史 → 发送消息（Markdown 渲染回答） */
import { onMounted, ref, watch } from 'vue'
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
const sending = ref(false)
const scrollRef = ref<HTMLElement | null>(null)

async function ensureAgents(): Promise<void> {
  if (!agents.value.length) {
    await agentStore.fetchList(1, 100)
    agents.value = agentStore.list
  }
}

/** 切换智能体：重置消息并加载历史 */
async function onAgentChange(agentIdValue: number): Promise<void> {
  chatStore.reset(agentIdValue)
  try {
    await chatStore.loadHistory(agentIdValue)
  } catch {
    notifyError('历史记录加载失败')
  }
  scrollToBottom()
}

async function onSend(): Promise<void> {
  const content = input.value.trim()
  if (!content || sending.value) return
  if (!selectedAgentId.value) {
    notifyError('请先选择智能体')
    return
  }
  sending.value = true
  input.value = ''
  try {
    await chatStore.send(content)
  } catch (e) {
    notifyError((e as Error).message)
  } finally {
    sending.value = false
    scrollToBottom()
  }
}

function scrollToBottom(): void {
  requestAnimationFrame(() => {
    if (scrollRef.value) scrollRef.value.scrollTop = scrollRef.value.scrollHeight
  })
}

watch(() => chatStore.messages.length, scrollToBottom)

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
            <div class="bubble">
              <MarkdownView v-if="msg.role === 'assistant'" :content="msg.content" />
              <template v-else>{{ msg.content }}</template>
              <div v-if="msg.role === 'assistant' && msg.sources?.length" class="sources">
                来源：{{ msg.sources.join('、') }}
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

.sources {
  margin-top: 6px;
  font-size: 12px;
  color: var(--color-text-secondary);
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
