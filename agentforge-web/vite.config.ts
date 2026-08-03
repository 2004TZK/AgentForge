import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// dev proxy：/api → 后端（后端 context-path=/api，原样透传）
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        // M4 代码分割：框架依赖独立分包（长缓存 + 消除 >500KB 主包警告）
        // element-plus 已按需引入（main.ts），不再整包分组，避免无用的 900KB 大 chunk
        manualChunks: {
          'vue-vendor': ['vue', 'vue-router', 'pinia'],
          http: ['axios'],
        },
      },
    },
  },
})
