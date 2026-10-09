<template>
  <div class="dashboard-page">
    <el-row :gutter="16">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">剩余额度</div>
          <div class="stat-value">{{ usage.quota_remaining }}</div>
          <div class="stat-extra">总配额 {{ usage.quota_total }} 次</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">已用额度</div>
          <div class="stat-value">{{ usage.quota_used }}</div>
          <div class="stat-extra">当前套餐：{{ planText }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">已授权店铺</div>
          <div class="stat-value">{{ shopCount }}</div>
          <div class="stat-extra">SP-API 授权店铺数量</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">生成任务</div>
          <div class="stat-value">{{ historyCount }}</div>
          <div class="stat-extra">累计生成记录条数</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="quick-card">
      <template #header><span class="section-title">快捷入口</span></template>
      <el-button type="primary" @click="go('/generate')">开始生成文案</el-button>
      <el-button @click="go('/shop-auth')">授权店铺</el-button>
      <el-button @click="go('/history')">查看历史记录</el-button>
      <el-button @click="go('/billing')">用量与计费</el-button>
    </el-card>

    <el-card class="recent-card">
      <template #header>
        <div class="header-row">
          <span class="section-title">最近生成记录</span>
          <el-button link type="primary" @click="go('/history')">查看全部</el-button>
        </div>
      </template>
      <el-table v-loading="loading" :data="recent" size="small" border>
        <el-table-column prop="created_at" label="生成时间" width="180">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="target_marketplace" label="站点" width="80" />
        <el-table-column label="标题预览" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">{{ row.result?.title || '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'success' ? 'success' : 'info'">
              {{ row.status === 'success' ? '成功' : row.status }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && !recent.length" description="还没有生成记录" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authApi, billingApi, errorMessage, generateApi } from '../api'
import type { GenerationRow, UsageRead } from '../types'

const router = useRouter()
const loading = ref(false)
const usage = ref<UsageRead>({
  plan: 'free',
  status: 'active',
  quota_total: 0,
  quota_used: 0,
  quota_remaining: 0
})
const shopCount = ref(0)
const rows = ref<GenerationRow[]>([])

const recent = computed(() => rows.value.slice(0, 5))
const historyCount = computed(() => rows.value.length)
const planText = computed(() => {
  const map: Record<string, string> = { free: '免费版', basic: '基础版', pro: '专业版' }
  return map[usage.value.plan] || usage.value.plan
})

const formatTime = (value: string): string => {
  if (!value) return '-'
  const date = new Date(value)
  const pad = (num: number) => String(num).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(
    date.getHours()
  )}:${pad(date.getMinutes())}`
}

const go = (path: string) => {
  router.push(path)
}

const load = async () => {
  loading.value = true
  try {
    const [usageData, shops, history] = await Promise.all([
      billingApi.usage(),
      authApi.shops(),
      generateApi.history(50)
    ])
    usage.value = usageData
    shopCount.value = shops.length
    rows.value = history
  } catch (error) {
    ElMessage.error(errorMessage(error, '加载工作台数据失败'))
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
})
</script>

<style scoped>
.stat-card {
  text-align: center;
}

.stat-label {
  font-size: 13px;
  color: #909399;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: #1890ff;
  margin: 8px 0;
}

.stat-extra {
  font-size: 12px;
  color: #c0c4cc;
}

.quick-card,
.recent-card {
  margin-top: 16px;
}

.section-title {
  font-weight: 600;
  color: #2d3748;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
