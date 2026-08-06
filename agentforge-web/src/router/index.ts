/** 路由与登录守卫：未登录访问受保护页面时跳转 /login */
import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from '../utils/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/agents' },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/auth/Login.vue'),
      meta: { public: true, title: '登录' },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('../views/auth/Register.vue'),
      meta: { public: true, title: '注册' },
    },
    {
      path: '/agents',
      name: 'agent-list',
      component: () => import('../views/agent/AgentList.vue'),
      meta: { title: '智能体列表' },
    },
    {
      path: '/agents/new',
      name: 'agent-create',
      component: () => import('../views/agent/AgentEdit.vue'),
      meta: { title: '新建智能体' },
    },
    {
      path: '/agents/:id/edit',
      name: 'agent-edit',
      component: () => import('../views/agent/AgentEdit.vue'),
      meta: { title: '编辑智能体' },
    },
    {
      path: '/chat',
      name: 'chat',
      component: () => import('../views/chat/ChatView.vue'),
      meta: { title: '聊天' },
    },
    {
      path: '/chat/:agentId',
      name: 'chat-agent',
      component: () => import('../views/chat/ChatView.vue'),
      meta: { title: '聊天' },
    },
    {
      path: '/files',
      name: 'files',
      component: () => import('../views/file/FileManage.vue'),
      meta: { title: '文件管理' },
    },
    {
      path: '/tools',
      name: 'tool-list',
      component: () => import('../views/tool/ToolList.vue'),
      meta: { title: '工具库' },
    },
    {
      path: '/tools/new',
      name: 'tool-create',
      component: () => import('../views/tool/ToolEdit.vue'),
      meta: { title: '新建工具' },
    },
    {
      path: '/tools/:id/edit',
      name: 'tool-edit',
      component: () => import('../views/tool/ToolEdit.vue'),
      meta: { title: '编辑工具' },
    },
    {
      path: '/workflows',
      name: 'workflow-list',
      component: () => import('../views/workflow/WorkflowList.vue'),
      meta: { title: '工作流列表' },
    },
    {
      path: '/workflows/new',
      name: 'workflow-create',
      component: () => import('../views/workflow/WorkflowEdit.vue'),
      meta: { title: '新建工作流' },
    },
    {
      path: '/workflows/:id/edit',
      name: 'workflow-edit',
      component: () => import('../views/workflow/WorkflowEdit.vue'),
      meta: { title: '编辑工作流' },
    },
    {
      path: '/models',
      name: 'model-provider-list',
      component: () => import('../views/model/ModelProviderList.vue'),
      meta: { title: '模型 Provider' },
    },
  ],
})

router.beforeEach((to) => {
  if (!to.meta.public && !getToken()) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.meta.public && getToken()) {
    return { path: '/agents' }
  }
  document.title = `${String(to.meta.title ?? '')} - AgentForge`
  return true
})

// 切换提速：页面空闲时预取全部懒加载路由 chunk，
// 首次点击导航栏不再等待 chunk 网络加载，页面切换接近即时。
if (typeof window !== 'undefined') {
  const prefetchRoutes = (): void => {
    router.getRoutes().forEach((route) => {
      const comp = route.components?.default
      if (typeof comp === 'function') {
        comp().catch(() => {
          /* 预取失败不影响正常导航 */
        })
      }
    })
  }
  window.addEventListener('load', () => {
    if ('requestIdleCallback' in window) {
      window.requestIdleCallback(prefetchRoutes)
    } else {
      window.setTimeout(prefetchRoutes, 500)
    }
  })
}

export default router
