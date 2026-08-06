import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// dev proxy：/api → 后端（后端 context-path=/api，原样透传）
// 默认指向本机后端 8080（README 本地开发）；后端跑在 Docker 时用环境变量指到 nginx 入口：
//   VITE_API_PROXY=https://localhost npm run dev
const apiTarget = process.env.VITE_API_PROXY || 'http://localhost:8080'
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        secure: false, // 允许自签 HTTPS（VITE_API_PROXY 指向 nginx 时）
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        // M4 代码分割：框架依赖独立分包（长缓存 + 消除 >500KB 主包警告）
        // 全站使用原生控件（main.ts 未引入第三方 UI 库），Element Plus 依赖已移除
        manualChunks: {
          'vue-vendor': ['vue', 'vue-router', 'pinia'],
          http: ['axios'],
        },
      },
    },
  },
})
