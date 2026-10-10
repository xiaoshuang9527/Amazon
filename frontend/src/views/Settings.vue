<template>
  <div class="page">
    <el-row :gutter="16">
      <el-col :span="12">
        <el-card>
          <template #header><span class="title">修改密码</span></template>
          <el-form :model="pwdForm" label-width="100px">
            <el-form-item label="当前密码">
              <el-input v-model="pwdForm.oldPassword" type="password" show-password />
            </el-form-item>
            <el-form-item label="新密码">
              <el-input v-model="pwdForm.newPassword" type="password" show-password />
            </el-form-item>
            <el-form-item label="确认新密码">
              <el-input v-model="pwdForm.confirmPassword" type="password" show-password />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="saving" @click="handleChangePassword">保存</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card>
          <template #header><span class="title">我的额度</span></template>
          <el-descriptions :column="1" border v-loading="usageLoading">
            <el-descriptions-item label="当前套餐">{{ planLabel }}</el-descriptions-item>
            <el-descriptions-item label="本月配额">{{ usage.quota_total }}</el-descriptions-item>
            <el-descriptions-item label="已使用">{{ usage.quota_used }}</el-descriptions-item>
            <el-descriptions-item label="剩余额度">{{ usage.quota_remaining }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { authApi, billingApi, errorMessage } from '../api'
import type { UsageRead } from '../types'

const pwdForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const saving = ref(false)
const usageLoading = ref(false)
const usage = reactive<UsageRead>({
  plan: 'free',
  status: 'active',
  quota_total: 0,
  quota_used: 0,
  quota_remaining: 0
})

const PLAN_LABELS: Record<string, string> = { free: '免费版', basic: '基础版', pro: '专业版' }
const planLabel = computed(() => PLAN_LABELS[usage.plan] || usage.plan)

const handleChangePassword = async () => {
  if (!pwdForm.oldPassword || !pwdForm.newPassword) {
    ElMessage.warning('请填写完整密码信息')
    return
  }
  if (pwdForm.newPassword !== pwdForm.confirmPassword) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  if (pwdForm.newPassword.length < 6) {
    ElMessage.warning('新密码至少 6 位')
    return
  }
  saving.value = true
  try {
    await authApi.changePassword(pwdForm.oldPassword, pwdForm.newPassword)
    ElMessage.success('密码修改成功')
    pwdForm.oldPassword = ''
    pwdForm.newPassword = ''
    pwdForm.confirmPassword = ''
  } catch (error) {
    ElMessage.error(errorMessage(error, '密码修改失败'))
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  usageLoading.value = true
  try {
    Object.assign(usage, await billingApi.usage())
  } catch (error) {
    ElMessage.error(errorMessage(error, '加载额度失败'))
  } finally {
    usageLoading.value = false
  }
})
</script>

<style scoped>
.page { padding: 8px; }
.title { font-weight: 600; }
</style>
