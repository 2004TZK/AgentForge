<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../../stores/auth'

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
    ElMessage.error('用户名至少 3 个字符')
    return
  }
  if (form.password.length < 6) {
    ElMessage.error('密码至少 6 位')
    return
  }
  if (form.password !== form.confirmPassword) {
    ElMessage.error('两次输入的密码不一致')
    return
  }
  submitting.value = true
  try {
    await authStore.register(form.username.trim(), form.password, form.email.trim() || undefined)
    ElMessage.success('注册成功，请登录')
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
      <h1 class="auth-title">注册账号</h1>
      <p class="muted">创建 AgentForge 账号</p>
      <el-form label-position="top" @submit.prevent="onSubmit">
        <el-form-item label="用户名">
          <el-input
            v-model="form.username"
            placeholder="3-20 位字母、数字或下划线"
            autocomplete="username"
          />
        </el-form-item>
        <el-form-item label="邮箱（可选）">
          <el-input v-model="form.email" placeholder="you@example.com" autocomplete="email" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            placeholder="至少 6 位"
            autocomplete="new-password"
          />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            show-password
            placeholder="再次输入密码"
            autocomplete="new-password"
          />
        </el-form-item>
        <el-button class="auth-submit" type="primary" native-type="submit" :loading="submitting">
          注册
        </el-button>
      </el-form>
      <p class="muted auth-switch">
        已有账号？<router-link to="/login">去登录</router-link>
      </p>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(160deg, #eff6ff 0%, #f5f6f8 100%);
}

.auth-card {
  width: 360px;
  padding: 32px;
}

.auth-title {
  margin: 0 0 4px;
  font-size: 22px;
}

.auth-submit {
  width: 100%;
  margin-top: 8px;
}

.auth-switch {
  margin-top: 16px;
  text-align: center;
}
</style>
