<template>
  <div class="page">
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card shadow="never">
          <div class="stat-label">用户总数</div>
          <div class="stat-value">{{ stats.users }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <div class="stat-label">管理员</div>
          <div class="stat-value">{{ stats.admins }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <div class="stat-label">Listing</div>
          <div class="stat-value">{{ stats.listings }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never">
          <div class="stat-label">生成记录</div>
          <div class="stat-value">{{ stats.generations }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span class="title">用户管理</span>
          <el-button :icon="undefined" size="small" @click="reload" :loading="loading">刷新</el-button>
        </div>
      </template>

      <el-table :data="users" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="email" label="邮箱" min-width="220" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '已禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="角色" width="120">
          <template #default="{ row }">
            <el-tag :type="row.is_admin ? 'warning' : 'info'" size="small">
              {{ row.is_admin ? '管理员' : '普通用户' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="注册时间" width="200">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="启用" width="90">
          <template #default="{ row }">
            <el-switch
              :model-value="row.is_active"
              :disabled="row.id === currentUserId"
              @change="(val: boolean) => toggle(row, 'is_active', val)"
            />
          </template>
        </el-table-column>
        <el-table-column label="管理员" width="100">
          <template #default="{ row }">
            <el-switch
              :model-value="row.is_admin"
              :disabled="row.id === currentUserId"
              @change="(val: boolean) => toggle(row, 'is_admin', val)"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="resetPassword(row)">
              重置密码
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          layout="total, prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi, errorMessage } from '../api'
import { useAuthStore } from '../stores/auth'
import type { AdminUserRow } from '../types'

const authStore = useAuthStore()
const currentUserId = computed(() => authStore.user?.id ?? -1)

const loading = ref(false)
const users = ref<AdminUserRow[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 50

const stats = reactive({ users: 0, admins: 0, listings: 0, generations: 0 })

const formatTime = (value?: string) => {
  if (!value) return '-'
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString()
}

async function loadStats() {
  try {
    Object.assign(stats, await adminApi.stats())
  } catch (error) {
    ElMessage.error(errorMessage(error, '加载统计失败'))
  }
}

async function loadUsers() {
  loading.value = true
  try {
    const data = await adminApi.users(pageSize, (page.value - 1) * pageSize)
    users.value = data.items
    total.value = data.total
  } catch (error) {
    ElMessage.error(errorMessage(error, '加载用户列表失败'))
  } finally {
    loading.value = false
  }
}

async function reload() {
  await Promise.all([loadStats(), loadUsers()])
}

async function toggle(row: AdminUserRow, field: 'is_active' | 'is_admin', value: boolean) {
  const label = field === 'is_active' ? '启用状态' : '管理员权限'
  try {
    const updated = await adminApi.update(row.id, { [field]: value })
    Object.assign(row, updated)
    ElMessage.success(`已更新 ${row.email} 的${label}`)
    await loadStats()
  } catch (error) {
    ElMessage.error(errorMessage(error, `更新${label}失败`))
  }
}

function handlePageChange(next: number) {
  page.value = next
  loadUsers()
}

async function resetPassword(row: AdminUserRow) {
  try {
    const { value } = await ElMessageBox.prompt(
      `为 ${row.email} 设置新密码（至少 6 位）`,
      '重置密码',
      {
        confirmButtonText: '确认重置',
        cancelButtonText: '取消',
        inputType: 'password',
        inputPlaceholder: '请输入新密码',
        inputValidator: (val: string) => (val && val.length >= 6) || '密码至少 6 位'
      }
    )
    await adminApi.resetPassword(row.id, value)
    ElMessage.success(`已重置 ${row.email} 的密码`)
  } catch (error) {
    // 用户点“取消”时 element-plus 会 reject，这里不当作错误提示
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(errorMessage(error, '重置密码失败'))
  }
}

onMounted(reload)
</script>

<style scoped>
.page {
  padding: 8px;
}

.stat-row {
  margin-bottom: 16px;
}

.stat-label {
  color: #909399;
  font-size: 13px;
}

.stat-value {
  font-size: 26px;
  font-weight: 600;
  color: #303133;
  margin-top: 6px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.title {
  font-weight: 600;
}

.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
