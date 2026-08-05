<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import ForgeMark from '../common/ForgeMark.vue'
import { useAuthStore } from '../../stores/auth'

const route = useRoute()
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
      <router-link to="/agents" class="wordmark">
        <ForgeMark :size="26" />
        <span class="wordmark-text">AGENTFORGE</span>
      </router-link>

      <nav class="nav" aria-label="主导航">
        <router-link to="/agents" class="nav-link">智能体</router-link>
        <router-link to="/chat" class="nav-link">对话</router-link>
        <router-link to="/files" class="nav-link">文件</router-link>
        <router-link to="/workflows" class="nav-link">工作流</router-link>
        <router-link to="/models" class="nav-link">模型</router-link>
      </nav>

      <div class="sidebar-foot">
        <span class="mono-mini">v1.0.0 · MIT</span>
        <span class="mono-mini">FORGE YOUR AGENTS</span>
      </div>
    </aside>

    <div class="main">
      <header class="topbar">
        <span class="crumb mono-mini">
          <span class="crumb-root">WORKSHOP</span>
          <span class="crumb-sep">/</span>
          <span class="crumb-page">{{ route.meta.title ?? '' }}</span>
        </span>
        <div class="user-area">
          <span class="username mono-mini">{{ authStore.user?.username ?? 'ANON' }}</span>
          <button class="btn btn-secondary btn-sm" @click="logout">退出</button>
        </div>
      </header>
      <main class="content">
        <slot />
      </main>
    </div>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  height: 100%;
}

/* ---- 锻黑侧栏 ---- */
.sidebar {
  width: 216px;
  background: var(--ink-deep);
  color: var(--card);
  padding: 18px 14px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 26px;
}

.wordmark {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 2px 6px;
  text-decoration: none;
}

.wordmark-text {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.24em;
  color: var(--card);
}

.nav {
  display: flex;
  flex-direction: column;
  gap: 3px;
  flex: 1;
}

.nav-link {
  position: relative;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  color: rgba(255, 253, 247, 0.62);
  font-size: 14px;
  text-decoration: none;
  transition: background 0.15s, color 0.15s;
}

.nav-link:hover {
  background: var(--ink-soft);
  color: var(--card);
}

/* 激活 = 烙上锻火标记 */
.nav-link.router-link-active {
  background: var(--ink);
  color: var(--card);
  font-weight: 600;
}

.nav-link.router-link-active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 20%;
  bottom: 20%;
  width: 3px;
  border-radius: 2px;
  background: var(--forge-glow);
}

.sidebar-foot {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 0 6px;
  color: rgba(255, 253, 247, 0.35);
}

.mono-mini {
  font-family: var(--font-mono);
  font-size: 10.5px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

/* ---- 主区 ---- */
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.topbar {
  height: 52px;
  background: var(--card);
  border-bottom: 1px solid var(--line);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}

.crumb {
  color: var(--steel);
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
}

.crumb-page {
  overflow: hidden;
  text-overflow: ellipsis;
}

.crumb-root {
  color: var(--forge);
}

.crumb-sep {
  opacity: 0.6;
}

.user-area {
  display: flex;
  align-items: center;
  gap: 12px;
}

.username {
  color: var(--steel);
}

.content {
  flex: 1;
  overflow-y: auto;
}

/* ---- 响应式：窄屏收成顶栏 ---- */
@media (max-width: 860px) {
  .layout {
    flex-direction: column;
  }

  .sidebar {
    width: 100%;
    flex-direction: row;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
  }

  .wordmark-text {
    display: none;
  }

  .nav {
    flex-direction: row;
    flex: 1;
    overflow-x: auto;
  }

  .nav-link {
    white-space: nowrap;
    padding: 7px 12px;
  }

  .nav-link.router-link-active::before {
    left: 10%;
    right: 10%;
    top: auto;
    bottom: 2px;
    width: auto;
    height: 2px;
  }

  .sidebar-foot {
    display: none;
  }

  .crumb-root,
  .crumb-sep {
    display: none;
  }
}
</style>
