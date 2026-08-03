<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

function logout(): void {
  authStore.logout()
  router.push('/login')
}
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="logo">⚙️ AgentForge</div>
      <nav class="nav">
        <router-link to="/agents" class="nav-link">智能体</router-link>
        <router-link to="/chat" class="nav-link">聊天</router-link>
        <router-link to="/files" class="nav-link">文件</router-link>
      </nav>
    </aside>
    <div class="main">
      <header class="topbar">
        <span class="muted">智能体快速搭建与对话平台</span>
        <div class="user-area">
          <span class="username">{{ authStore.user?.username ?? '未登录' }}</span>
          <button class="btn btn-secondary btn-sm" @click="logout">退出</button>
        </div>
      </header>
      <main class="content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  height: 100%;
}

.sidebar {
  width: 200px;
  background: #111827;
  color: #fff;
  padding: 16px 12px;
  flex-shrink: 0;
}

.logo {
  font-size: 16px;
  font-weight: 700;
  padding: 8px 12px 20px;
}

.nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-link {
  padding: 10px 12px;
  border-radius: 6px;
  color: #d1d5db;
  font-size: 14px;
}

.nav-link:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #fff;
}

.nav-link.router-link-active {
  background: var(--color-primary);
  color: #fff;
}

.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.topbar {
  height: 52px;
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}

.user-area {
  display: flex;
  align-items: center;
  gap: 12px;
}

.username {
  font-weight: 500;
}

.content {
  flex: 1;
  overflow-y: auto;
}
</style>
