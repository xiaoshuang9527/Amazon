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
              <el-button type="primary" @click="handleChangePassword">保存</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card>
          <template #header><span class="title">API 用量</span></template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="本月生成次数">{{ apiUsage.generations }}</el-descriptions-item>
            <el-descriptions-item label="消耗 Token">{{ apiUsage.tokens }}</el-descriptions-item>
            <el-descriptions-item label="预估成本">¥{{ apiUsage.cost }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import { ElMessage } from 'element-plus'

const pwdForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const apiUsage = reactive({
  generations: 0,
  tokens: 0,
  cost: '0.00'
})

const handleChangePassword = () => {
  if (!pwdForm.oldPassword || !pwdForm.newPassword) {
    ElMessage.warning('请填写完整密码信息')
    return
  }
  if (pwdForm.newPassword !== pwdForm.confirmPassword) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  // TODO: 调用 PUT /auth/password
  ElMessage.success('密码修改成功')
}
</script>

<style scoped>
.page { padding: 8px; }
.title { font-weight: 600; }
</style>