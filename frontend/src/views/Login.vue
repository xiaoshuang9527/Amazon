<template>
  <div class="login-container">
    <el-card class="login-card">
      <template #header>
        <div class="card-header">
          <h2>亚马逊 Listing 多语言文案生成工具</h2>
          <p>{{ mode === 'login' ? '登录' : '注册新账号' }}</p>
        </div>
      </template>

      <el-tabs v-model="mode" stretch class="mode-tabs">
        <el-tab-pane label="登录" name="login" />
        <el-tab-pane label="注册" name="register" />
      </el-tabs>

      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px" @keyup.enter="handleSubmit">
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="请输入邮箱" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码（至少 6 位）"
            show-password
            autocomplete="current-password"
          />
        </el-form-item>
        <el-form-item v-if="mode === 'register'" label="确认密码" prop="confirm">
          <el-input v-model="form.confirm" type="password" placeholder="请再次输入密码" show-password />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="submitting" style="width: 100%" @click="handleSubmit">
            {{ mode === 'login' ? '登录' : '注册并登录' }}
          </el-button>
        </el-form-item>
      </el-form>

      <div class="hint">
        登录成功后将进入工作台，令牌由后端签发并在本地保存，刷新页面自动恢复登录态。
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuthStore } from '../stores/auth'
import { errorMessage } from '../api'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const mode = ref<'login' | 'register'>('login')
const formRef = ref<FormInstance>()
const submitting = ref(false)

const form = reactive({
  email: '',
  password: '',
  confirm: ''
})

const rules: FormRules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' }
  ],
  confirm: [
    {
      validator: (_rule: any, value: any, callback: any) => {
        if (mode.value === 'register' && value !== form.password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

watch(mode, () => {
  formRef.value?.clearValidate()
})

const handleSubmit = async () => {
  if (!formRef.value) return
  const valid = await formRef.value
    .validate()
    .then(() => true)
    .catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (mode.value === 'register') {
      await authStore.register(form.email, form.password)
      ElMessage.success('注册成功，正在登录')
    }
    const profile = await authStore.login(form.email, form.password)
    ElMessage.success(`欢迎回来，${profile.nickname}`)
    const redirect = (route.query.redirect as string) || '/dashboard'
    router.replace(redirect)
  } catch (error) {
    ElMessage.error(errorMessage(error, mode.value === 'register' ? '注册失败' : '登录失败'))
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-card {
  width: 440px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
  border-radius: 12px;
}

.card-header {
  text-align: center;
}

.card-header h2 {
  margin: 0 0 8px;
  font-size: 20px;
  color: #2d3748;
}

.card-header p {
  margin: 0;
  color: #718096;
  font-size: 14px;
}

.mode-tabs {
  margin-bottom: 12px;
}

.hint {
  color: #909399;
  font-size: 12px;
  line-height: 1.6;
  text-align: center;
}
</style>
