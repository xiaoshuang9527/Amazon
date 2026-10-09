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

      <el-table :data="shops" border style="width: 100%">
        <el-table-column prop="sellerId" label="卖家 ID" width="200" />
        <el-table-column prop="marketplaces" label="站点" min-width="200">
          <template #default="{ row }">
            <el-tag v-for="m in row.marketplaces" :key="m" style="margin-right: 6px">{{ m }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'warning'">
              {{ row.status === 'active' ? '已授权' : '已过期' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="授权时间" width="180" />
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button size="small" @click="handleReauthorize(row)">重新授权</el-button>
            <el-button size="small" type="danger" @click="handleRevoke(row)">解除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="shops.length === 0" description="暂无已授权店铺，点击右上角按钮开始授权" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const shops = ref<any[]>([])

onMounted(() => {
  // TODO: 调用 GET /auth/spapi/shops 获取店铺列表
})

const handleAuthorize = async () => {
  // TODO: 调用 GET /auth/spapi/authorize 获取授权 URL 并跳转
  ElMessage.info('正在获取 SP-API 授权链接...')
}

const handleReauthorize = (row: any) => {
  ElMessage.info(`重新授权店铺 ${row.sellerId}`)
}

const handleRevoke = (row: any) => {
  ElMessageBox.confirm('确认解除该店铺授权？解除后将无法读取该店铺的 Listing。', '提示', {
    type: 'warning'
  }).then(() => {
    ElMessage.success('已解除授权')
  }).catch(() => {})
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
</style>