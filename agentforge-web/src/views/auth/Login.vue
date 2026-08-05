<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ForgeMark from '../../components/common/ForgeMark.vue'
import { useAuthStore } from '../../stores/auth'
import { notifyError } from '../../utils/notify'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const form = reactive({ username: '', password: '' })
const showPassword = ref(false)
const submitting = ref(false)

async function onSubmit(): Promise<void> {
  if (!form.username || !form.password) {
    notifyError('请输入用户名和密码')
    return
  }
  submitting.value = true
  try {
    await authStore.login(form.username.trim(), form.password)
    const redirect = (route.query.redirect as string) || '/agents'
    router.push(redirect)
  } catch {
    // 错误提示已由响应拦截器统一处理
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-card card">
      <div class="auth-brand">
        <ForgeMark :size="44" />
        <div class="auth-wordmark">AGENTFORGE</div>
      </div>
      <p class="auth-eyebrow">Workshop · Sign In</p>

      <form class="auth-form" @submit.prevent="onSubmit">
        <div class="form-item">
          <label for="username">用户名</label>
          <input
            id="username"
            v-model="form.username"
            class="input"
            placeholder="请输入用户名"
            autocomplete="username"
          />
        </div>
        <div class="form-item">
          <label for="password">密码</label>
          <div class="password-wrap">
            <input
              id="password"
              v-model="form.password"
              class="input"
              :type="showPassword ? 'text' : 'password'"
              placeholder="请输入密码"
              autocomplete="current-password"
            />
            <button
              type="button"
              class="password-toggle"
              :aria-label="showPassword ? '隐藏密码' : '显示密码'"
              @click="showPassword = !showPassword"
            >
              {{ showPassword ? '隐藏' : '显示' }}
            </button>
          </div>
        </div>
        <button class="btn auth-submit" type="submit" :disabled="submitting">
          {{ submitting ? '正在进入…' : '进入工坊' }}
        </button>
      </form>

      <p class="muted auth-switch">
        还没有账号？<router-link to="/register">立即注册</router-link>
      </p>
      <p class="auth-footer">Open Source · MIT — Forge Your Agents</p>
    </div>
  </div>
</template>

<style scoped>
.password-wrap {
  position: relative;
}

.password-toggle {
  position: absolute;
  right: 4px;
  top: 50%;
  transform: translateY(-50%);
  border: none;
  background: transparent;
  color: var(--steel);
  font-size: 12px;
  cursor: pointer;
  padding: 6px 8px;
  border-radius: 4px;
}

.password-toggle:hover {
  color: var(--forge);
}
</style>
