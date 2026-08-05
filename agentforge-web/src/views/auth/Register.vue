<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import ForgeMark from '../../components/common/ForgeMark.vue'
import { useAuthStore } from '../../stores/auth'
import { notifyError, notifySuccess } from '../../utils/notify'

const router = useRouter()
const authStore = useAuthStore()

const form = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
})
const submitting = ref(false)

async function onSubmit(): Promise<void> {
  if (form.username.trim().length < 3) {
    notifyError('用户名至少 3 个字符')
    return
  }
  if (form.password.length < 6) {
    notifyError('密码至少 6 位')
    return
  }
  if (form.password !== form.confirmPassword) {
    notifyError('两次输入的密码不一致')
    return
  }
  submitting.value = true
  try {
    await authStore.register(form.username.trim(), form.password, form.email.trim() || undefined)
    notifySuccess('注册成功，请登录')
    router.push('/login')
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
      <p class="auth-eyebrow">Workshop · Register</p>

      <form class="auth-form" @submit.prevent="onSubmit">
        <div class="form-item">
          <label for="username">用户名</label>
          <input
            id="username"
            v-model="form.username"
            class="input"
            placeholder="3-20 位字母、数字或下划线"
            autocomplete="username"
          />
        </div>
        <div class="form-item">
          <label for="email">邮箱（可选）</label>
          <input id="email" v-model="form.email" class="input" placeholder="you@example.com" autocomplete="email" />
        </div>
        <div class="form-item">
          <label for="password">密码</label>
          <input
            id="password"
            v-model="form.password"
            class="input"
            type="password"
            placeholder="至少 6 位"
            autocomplete="new-password"
          />
        </div>
        <div class="form-item">
          <label for="confirmPassword">确认密码</label>
          <input
            id="confirmPassword"
            v-model="form.confirmPassword"
            class="input"
            type="password"
            placeholder="再次输入密码"
            autocomplete="new-password"
          />
        </div>
        <button class="btn auth-submit" type="submit" :disabled="submitting">
          {{ submitting ? '正在创建…' : '创建账号' }}
        </button>
      </form>

      <p class="muted auth-switch">
        已有账号？<router-link to="/login">去登录</router-link>
      </p>
      <p class="auth-footer">Open Source · MIT — Forge Your Agents</p>
    </div>
  </div>
</template>
