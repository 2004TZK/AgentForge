import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

// M4 前端冒烟测试：jsdom 环境跑纯逻辑单测（无需浏览器）
export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'jsdom',
    include: ['src/**/*.spec.ts'],
  },
})
