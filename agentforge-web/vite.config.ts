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
})
