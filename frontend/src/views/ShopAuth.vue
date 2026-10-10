<template>
  <div class="page">
    <el-card>
      <template #header>
        <div class="card-title">
          <span>店铺授权</span>
          <el-button type="primary" @click="handleAuthorize">授权新店铺</el-button>
        </div>
      </template>

      <el-alert
        title="授权说明"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      >
        <p>通过 Amazon SP-API 官方接口授权，只读取你的 Listing 数据，不会修改任何内容。授权后 token 加密存储。</p>
      </el-alert>

      <el-table :data="shops" border style="width: 100%" v-loading="loading">
        <el-table-column prop="seller_id" label="卖家 ID" width="200" />
        <el-table-column label="站点" min-width="200">
          <template #default="{ row }">
            <el-tag v-for="m in row.marketplace_ids" :key="m" style="margin-right: 6px">{{ m }}</el-tag>
            <span v-if="!row.marketplace_ids?.length" class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'warning'">
              {{ row.status === 'active' ? '已授权' : '已过期' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="授权时间" width="180">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button size="small" @click="handleReauthorize(row)">重新授权</el-button>
            <el-button size="small" type="danger" @click="handleRevoke(row)">解除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && shops.length === 0" description="暂无已授权店铺，点击右上角按钮开始授权" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { authApi, errorMessage } from '../api'
import type { ShopRead } from '../types'

const shops = ref<ShopRead[]>([])
const loading = ref(false)

const formatTime = (value?: string) => {
  if (!value) return '-'
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString()
}

async function loadShops() {
  loading.value = true
  try {
    shops.value = await authApi.shops()
  } catch (error) {
    ElMessage.error(errorMessage(error, '加载店铺列表失败'))
  } finally {
    loading.value = false
  }
}

onMounted(loadShops)

const handleAuthorize = async () => {
  try {
    const { authorize_url, configured } = await authApi.authorizeUrl()
    if (!configured) {
      ElMessage.warning(
        '尚未配置 SP-API 凭据（SPAPI_CLIENT_ID / SPAPI_CLIENT_SECRET），授权链接暂时无法走通。'
      )
      return
    }
    window.open(authorize_url, '_blank')
  } catch (error) {
    ElMessage.error(errorMessage(error, '获取授权链接失败'))
  }
}

const handleReauthorize = async (row: ShopRead) => {
  await handleAuthorize()
}

const handleRevoke = async (row: ShopRead) => {
  try {
    await ElMessageBox.confirm('确认解除该店铺授权？解除后将无法读取该店铺的 Listing。', '提示', {
      type: 'warning'
    })
    await authApi.revokeShop(row.id)
    ElMessage.success('已解除授权')
    await loadShops()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(errorMessage(error, '解除授权失败'))
  }
}
</script>

<style scoped>
.page {
  padding: 8px;
}

.card-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
}

.muted {
  color: #c0c4cc;
}
</style>
