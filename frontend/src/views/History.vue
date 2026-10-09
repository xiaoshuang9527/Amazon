<template>
  <div class="history-page">
    <el-card>
      <template #header>
        <div class="header-row">
          <span class="title">历史记录</span>
          <div>
            <el-input
              v-model="keyword"
              size="small"
              placeholder="按任务 ID / 站点 / 标题过滤"
              style="width: 240px; margin-right: 8px"
              clearable
            />
            <el-button size="small" :loading="loading" @click="load">刷新</el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="filtered" border size="small">
        <el-table-column prop="created_at" label="生成时间" width="180">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="task_id" label="任务 ID" width="230" show-overflow-tooltip />
        <el-table-column prop="target_marketplace" label="站点" width="80" />
        <el-table-column label="标题预览" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ row.result?.title || '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDetail(row)">查看</el-button>
            <el-button
              v-for="format in exportFormats"
              :key="format.value"
              link
              type="primary"
              size="small"
              :loading="exporting === `${row.id}-${format.value}` && row.id !== undefined"
              @click="handleExport(row, format.value)"
            >
              {{ format.label }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="footer">共 {{ filtered.length }} 条生成记录</div>
    </el-card>

    <el-drawer v-model="detailVisible" title="生成结果详情" size="46%">
      <template v-if="current">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="任务 ID">{{ current.task_id }}</el-descriptions-item>
          <el-descriptions-item label="站点">{{ current.target_marketplace }}</el-descriptions-item>
          <el-descriptions-item label="目标语言">{{ current.target_language }}</el-descriptions-item>
          <el-descriptions-item label="模型">{{ current.model_used || '-' }}</el-descriptions-item>
          <el-descriptions-item label="Listing ID">{{ current.listing_id ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ statusText(current.status) }}</el-descriptions-item>
        </el-descriptions>

        <div class="detail-block">
          <h4>标题</h4>
          <p>{{ current.result?.title }}</p>
        </div>
        <div class="detail-block">
          <h4>五点描述</h4>
          <ul>
            <li v-for="(bullet, index) in current.result?.bullets || []" :key="index">{{ bullet }}</li>
          </ul>
        </div>
        <div class="detail-block">
          <h4>长描述</h4>
          <p class="pre">{{ current.result?.description }}</p>
        </div>
        <div class="detail-block">
          <h4>搜索词</h4>
          <p>{{ current.result?.search_terms }}</p>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { errorMessage, generateApi } from '../api'
import type { ExportFormat, GenerationRow } from '../types'

const exportFormats: { value: ExportFormat; label: string }[] = [
  { value: 'xlsx', label: 'Excel' },
  { value: 'json', label: 'JSON' },
  { value: 'csv', label: 'CSV' }
]

const loading = ref(false)
const exporting = ref('')
const keyword = ref('')
const rows = ref<GenerationRow[]>([])
const detailVisible = ref(false)
const current = ref<GenerationRow | null>(null)

const filtered = computed(() => {
  const key = keyword.value.trim().toLowerCase()
  if (!key) return rows.value
  return rows.value.filter((row) => {
    const title = String(row.result?.title || '').toLowerCase()
    return (
      row.task_id.toLowerCase().includes(key) ||
      row.target_marketplace.toLowerCase().includes(key) ||
      title.includes(key)
    )
  })
})

const formatTime = (value: string): string => {
  if (!value) return '-'
  const date = new Date(value)
  const pad = (num: number) => String(num).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(
    date.getHours()
  )}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

const statusType = (status: string) => {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  return 'info'
}

const statusText = (status: string) => {
  const map: Record<string, string> = {
    success: '成功',
    failed: '失败',
    running: '生成中',
    pending: '排队中',
    partial: '部分成功'
  }
  return map[status] || status
}

const load = async () => {
  loading.value = true
  try {
    rows.value = await generateApi.history(100)
  } catch (error) {
    ElMessage.error(errorMessage(error, '加载历史记录失败'))
  } finally {
    loading.value = false
  }
}

const openDetail = (row: GenerationRow) => {
  current.value = row
  detailVisible.value = true
}

const handleExport = async (row: GenerationRow, format: ExportFormat) => {
  exporting.value = `${row.id}-${format}`
  try {
    const blob = await generateApi.exportFile(row.task_id, format)
    const filename = `listing_${row.task_id}_${row.target_marketplace}.${format}`
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    ElMessage.success(`已导出 ${filename}`)
  } catch (error) {
    ElMessage.error(errorMessage(error, '导出失败'))
  } finally {
    exporting.value = ''
  }
}

onMounted(() => {
  load()
})
</script>

<style scoped>
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title {
  font-weight: 600;
}

.footer {
  margin-top: 12px;
  font-size: 13px;
  color: #909399;
}

.detail-block {
  margin-top: 16px;
  font-size: 13px;
  line-height: 1.7;
  color: #303133;
  word-break: break-word;
}

.detail-block h4 {
  margin: 0 0 6px;
  color: #2d3748;
}

.detail-block p {
  margin: 0;
}

.detail-block p.pre {
  white-space: pre-wrap;
}

.detail-block ul {
  margin: 0;
  padding-left: 18px;
}
</style>
