/** 智能体状态：列表 / 当前 Agent */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  apiAgentPage,
  apiCreateAgent,
  apiDeleteAgent,
  apiUpdateAgent,
} from '../api/agent'
import type { AgentDetail, AgentItem, AgentPayload } from '../types/agent'
import type { PageResult } from '../types/api'

export const useAgentStore = defineStore('agent', () => {
  const list = ref<AgentItem[]>([])
  const total = ref(0)
  const loading = ref(false)
  const current = ref<AgentDetail | null>(null)

  async function fetchList(page = 1, size = 10, name = ''): Promise<PageResult<AgentItem>> {
    loading.value = true
    try {
      const result = await apiAgentPage({ page, size, name })
      list.value = result.list
      total.value = result.total
      return result
    } finally {
      loading.value = false
    }
  }

  function setCurrent(agent: AgentDetail | null): void {
    current.value = agent
  }

  async function create(payload: AgentPayload): Promise<AgentDetail> {
    return apiCreateAgent(payload)
  }

  async function update(id: number, payload: AgentPayload): Promise<AgentDetail> {
    return apiUpdateAgent(id, payload)
  }

  async function remove(id: number): Promise<void> {
    await apiDeleteAgent(id)
  }

  return { list, total, loading, current, fetchList, setCurrent, create, update, remove }
})
