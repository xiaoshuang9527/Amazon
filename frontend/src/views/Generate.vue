<template>
  <div class="generate-page">
    <el-row :gutter="16">
      <!-- 左：产品信息输入 -->
      <el-col :span="7">
        <el-card class="panel">
          <template #header>
            <span class="panel-title">1. 产品信息输入</span>
          </template>

          <el-radio-group v-model="inputMode" style="margin-bottom: 12px" @change="handleInputModeChange">
            <el-radio-button label="manual">手动粘贴</el-radio-button>
            <el-radio-button label="listing">从 Listing 读取</el-radio-button>
          </el-radio-group>

          <el-form v-if="inputMode === 'listing'" label-position="top" size="small">
            <el-form-item label="选择已有 Listing">
              <el-select
                v-model="selectedListingId"
                placeholder="请选择要改写与回填的 Listing"
                style="width: 100%"
                :loading="listingLoading"
                @change="handleListingSelect"
              >
                <el-option
                  v-for="item in listings"
                  :key="item.id"
                  :label="listingLabel(item)"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>
          </el-form>

          <el-form label-position="top" size="small">
            <el-form-item label="产品标题">
              <el-input v-model="source.title" placeholder="请输入中文产品标题" />
            </el-form-item>
            <el-form-item label="五点描述（每行一条）">
              <el-input
                v-model="source.bulletsText"
                type="textarea"
                :rows="5"
                placeholder="每行一条产品卖点"
              />
            </el-form-item>
            <el-form-item label="产品长描述">
              <el-input
                v-model="source.description"
                type="textarea"
                :rows="5"
                placeholder="请输入产品详细描述"
              />
            </el-form-item>
            <el-form-item label="核心关键词（逗号或换行分隔）">
              <el-input v-model="source.keywordsText" placeholder="如：蓝牙耳机, 降噪" />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 中：生成参数与导出 -->
      <el-col :span="6">
        <el-card class="panel">
          <template #header>
            <span class="panel-title">2. 生成参数</span>
          </template>
          <el-form label-position="top" size="small">
            <el-form-item label="目标站点">
              <el-select v-model="targetMarketplaces" multiple style="width: 100%">
                <el-option
                  v-for="item in marketplaceOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="产品类目">
              <el-input v-model="category" placeholder="如：Electronics（默认 * 通用）" />
            </el-form-item>
            <el-form-item label="文案风格">
              <el-select v-model="tone" style="width: 100%">
                <el-option label="专业" value="professional" />
                <el-option label="友好" value="friendly" />
                <el-option label="热情" value="enthusiastic" />
                <el-option label="简洁" value="concise" />
              </el-select>
            </el-form-item>
            <el-form-item label="生成质量">
              <el-radio-group v-model="quality">
                <el-radio label="standard">标准</el-radio>
                <el-radio label="high">高质量</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-form>

          <el-button
            type="primary"
            style="width: 100%"
            :loading="loading"
            @click="handleGenerate"
          >
            {{ loading ? '生成中...' : '开始生成' }}
          </el-button>
          <el-progress
            v-if="loading"
            :percentage="progress"
            :stroke-width="6"
            style="margin-top: 12px"
          />

          <el-divider content-position="left">结果导出</el-divider>
          <div class="export-row">
            <el-button
              v-for="format in exportFormats"
              :key="format.value"
              size="small"
              :disabled="!taskId"
              :loading="exporting === format.value"
              @click="handleExport(format.value)"
            >
              {{ format.label }}
            </el-button>
          </div>
          <div class="export-tip">
            导出内容包含本次任务全部目标站点，格式遵循亚马逊 Flat File（Excel/CSV）与 SP-API Patch（JSON）。
          </div>
        </el-card>
      </el-col>

      <!-- 右：生成结果 -->
      <el-col :span="11">
        <el-card class="panel result-panel">
          <template #header>
            <div class="panel-header">
              <span class="panel-title">3. 生成结果</span>
              <el-tag v-if="taskId" size="small" type="info">任务：{{ taskId }}</el-tag>
            </div>
          </template>

          <el-empty v-if="!results.length" description="暂无生成结果，请先填写产品信息并点击开始生成" />
          <el-alert
            v-else-if="!listingId"
            type="warning"
            :closable="false"
            show-icon
            title="本次任务未绑定 Listing，回填功能不可用（可在「从 Listing 读取」模式下生成以启用回填）"
            style="margin-bottom: 12px"
          />

          <div v-for="item in results" :key="item.marketplace" class="result-item">
            <div class="result-header">
              <div class="result-title">
                <el-tag size="small" type="success">{{ item.marketplace }}</el-tag>
                <span class="lang">{{ item.target_language }}</span>
                <el-tag v-if="item.compliance_report?.passed" size="small">合规通过</el-tag>
                <el-tag v-else size="small" type="danger">
                  违规 {{ item.compliance_report?.violations?.length || 0 }} 项
                </el-tag>
                <el-tag v-if="appliedAt[item.marketplace]" size="small" type="warning">
                  已回填
                </el-tag>
              </div>
              <div class="result-actions">
                <el-button
                  size="small"
                  type="primary"
                  plain
                  :disabled="!listingId || !taskId"
                  @click="handleApply(item)"
                >
                  回填到 Listing
                </el-button>
              </div>
            </div>

            <div class="field">
              <label>标题</label>
              <p>{{ item.title }}</p>
            </div>
            <div class="field">
              <label>五点描述</label>
              <ul>
                <li v-for="(bullet, index) in item.bullets" :key="index">{{ bullet }}</li>
              </ul>
            </div>
            <div class="field">
              <label>长描述</label>
              <p class="pre">{{ item.description }}</p>
            </div>
            <div class="field">
              <label>搜索词</label>
              <p>{{ item.search_terms }}</p>
            </div>
            <div v-if="item.suggested_keywords?.length" class="field">
              <label>建议关键词</label>
              <div class="keywords">
                <el-tag
                  v-for="keyword in item.suggested_keywords"
                  :key="keyword"
                  size="small"
                  type="info"
                >
                  {{ keyword }}
                </el-tag>
              </div>
            </div>
            <div
              v-if="!item.compliance_report?.passed && item.compliance_report?.violations?.length"
              class="violations"
            >
              <el-alert type="error" :closable="false" show-icon title="合规提示">
                <div v-for="(v, i) in item.compliance_report.violations" :key="i">
                  {{ v.type }}：{{ v.word || v.field }} {{ v.suggestion || v.message }}
                </div>
              </el-alert>
            </div>
          </div>

          <el-alert
            v-if="taskErrors.length"
            type="warning"
            :closable="false"
            show-icon
            title="部分站点生成失败"
            style="margin-top: 12px"
          >
            <div v-for="(message, index) in taskErrors" :key="index">{{ message }}</div>
          </el-alert>
        </el-card>
      </el-col>
    </el-row>

    <ListingDiffDialog
      v-model="diffVisible"
      :listing-id="listingId"
      :task-id="taskId"
      :marketplace="diffMarketplace"
      :seed="diffSeed"
      @applied="handleApplied"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { errorMessage, generateApi, listingsApi } from '../api'
import ListingDiffDialog from '../components/ListingDiffDialog.vue'
import type {
  ApplyResponse,
  ExportFormat,
  GeneratedListing,
  GeneratedResultView,
  ListingRow,
  TaskStatus
} from '../types'

const marketplaceOptions = [
  { value: 'US', label: '美国 (US · 英语)' },
  { value: 'UK', label: '英国 (UK · 英语)' },
  { value: 'DE', label: '德国 (DE · 德语)' },
  { value: 'FR', label: '法国 (FR · 法语)' },
  { value: 'ES', label: '西班牙 (ES · 西语)' },
  { value: 'IT', label: '意大利 (IT · 意语)' },
  { value: 'JP', label: '日本 (JP · 日语)' },
  { value: 'CA', label: '加拿大 (CA · 英语)' },
  { value: 'MX', label: '墨西哥 (MX · 西语)' }
]

const exportFormats: { value: ExportFormat; label: string }[] = [
  { value: 'xlsx', label: '导出 Excel' },
  { value: 'json', label: '导出 JSON' },
  { value: 'csv', label: '导出 CSV' }
]

const inputMode = ref<'manual' | 'listing'>('manual')
const listings = ref<ListingRow[]>([])
const listingLoading = ref(false)
const selectedListingId = ref<number | null>(null)

const source = reactive({
  title: '',
  bulletsText: '',
  description: '',
  keywordsText: ''
})

const targetMarketplaces = ref<string[]>(['US'])
const category = ref('*')
const tone = ref('professional')
const quality = ref('standard')

const loading = ref(false)
const progress = ref(0)
const taskId = ref('')
const listingId = ref<number | null>(null)
const results = ref<GeneratedResultView[]>([])
const taskErrors = ref<string[]>([])
const exporting = ref<ExportFormat | ''>('')
const appliedAt = ref<Record<string, string>>({})

const diffVisible = ref(false)
const diffMarketplace = ref('')
const diffSeed = ref<Record<string, any> | null>(null)

const toView = (item: GeneratedListing): GeneratedResultView => ({
  ...item,
  marketplace: item.target_marketplace
})

const listingLabel = (item: ListingRow): string => {
  const content = item.source_content || {}
  const title = content.title || '未命名产品'
  return `#${item.id} ${title}（${item.marketplace_id || item.source_language || '-'}）`
}

const loadListings = async () => {
  listingLoading.value = true
  try {
    listings.value = await listingsApi.list()
  } catch (error) {
    ElMessage.error(errorMessage(error, '加载 Listing 列表失败'))
  } finally {
    listingLoading.value = false
  }
}

const handleInputModeChange = (value: string | number | boolean | undefined) => {
  if (value === 'manual') {
    selectedListingId.value = null
    listingId.value = null
  }
}

const handleListingSelect = (id: number) => {
  const target = listings.value.find((item) => item.id === id)
  if (!target) return
  const content = target.source_content || {}
  source.title = content.title || ''
  source.bulletsText = (content.bullets || []).join('\n')
  source.description = content.description || ''
  source.keywordsText = (content.keywords || []).join(', ')
  listingId.value = target.id
}

const buildPayload = () => ({
  listing_id: inputMode.value === 'listing' ? selectedListingId.value : null,
  source_content: {
    title: source.title.trim(),
    bullets: source.bulletsText
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean),
    description: source.description.trim(),
    keywords: source.keywordsText
      .split(/[,，\n]/)
      .map((item) => item.trim())
      .filter(Boolean),
    attributes: {}
  },
  target_marketplaces: targetMarketplaces.value,
  category: category.value.trim() || '*',
  tone: tone.value,
  quality: quality.value
})

const pollTask = async (id: string): Promise<TaskStatus> => {
  const terminal = ['success', 'failed', 'partial']
  let latest = await generateApi.status(id)
  for (let i = 0; i < 40 && !terminal.includes(latest.status); i += 1) {
    await new Promise((resolve) => setTimeout(resolve, 1500))
    progress.value = Math.min(95, 55 + i * 2)
    latest = await generateApi.status(id)
  }
  return latest
}

const handleGenerate = async () => {
  if (!source.title.trim()) {
    ElMessage.warning('请先填写产品标题')
    return
  }
  if (!targetMarketplaces.value.length) {
    ElMessage.warning('请至少选择一个目标站点')
    return
  }
  if (inputMode.value === 'listing' && !selectedListingId.value) {
    ElMessage.warning('请选择要处理的 Listing')
    return
  }

  loading.value = true
  progress.value = 10
  results.value = []
  taskErrors.value = []
  appliedAt.value = {}

  try {
    const created = await generateApi.submit(buildPayload())
    taskId.value = created.task_id
    progress.value = 50
    const task = await pollTask(created.task_id)
    listingId.value = task.listing_id ?? listingId.value
    taskErrors.value = task.errors || []
    results.value = (task.results || []).map(toView)
    if (results.value.length) {
      ElMessage.success(`生成完成，共 ${results.value.length} 个站点`)
    } else {
      ElMessage.warning('任务已提交，暂未返回结果，请稍后在历史记录中查看')
    }
  } catch (error) {
    ElMessage.error(errorMessage(error, '生成失败'))
  } finally {
    loading.value = false
    progress.value = 0
  }
}

const handleExport = async (format: ExportFormat) => {
  if (!taskId.value) {
    ElMessage.warning('请先生成文案后再导出')
    return
  }
  exporting.value = format
  try {
    const blob = await generateApi.exportFile(taskId.value, format)
    const filename = `listing_${taskId.value}.${format}`
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

const handleApply = (item: GeneratedResultView) => {
  if (!listingId.value || !taskId.value) {
    ElMessage.warning('缺少 Listing 或任务信息，无法回填')
    return
  }
  diffMarketplace.value = item.marketplace
  diffSeed.value = {
    title: item.title,
    bullets: item.bullets,
    description: item.description,
    search_terms: item.search_terms
  }
  diffVisible.value = true
}

const handleApplied = (response: ApplyResponse) => {
  appliedAt.value[response.marketplace_id] = response.applied_at || new Date().toISOString()
  if (selectedListingId.value === response.listing_id) {
    loadListings()
  }
}

onMounted(() => {
  loadListings()
})
</script>

<style scoped>
.generate-page {
  padding-bottom: 24px;
}

.panel {
  min-height: 640px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.panel-title {
  font-weight: 600;
  color: #2d3748;
}

.export-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.export-tip {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
  line-height: 1.6;
}

.result-item {
  border-bottom: 1px dashed #e4e7ed;
  padding: 12px 0;
}

.result-item:last-child {
  border-bottom: none;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.result-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.result-title .lang {
  font-size: 12px;
  color: #909399;
}

.field {
  margin-bottom: 8px;
}

.field label {
  display: block;
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.field p {
  margin: 0;
  font-size: 13px;
  color: #303133;
  line-height: 1.7;
  word-break: break-word;
}

.field p.pre {
  white-space: pre-wrap;
}

.field ul {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  color: #303133;
  line-height: 1.7;
}

.keywords {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.violations {
  margin-top: 8px;
  font-size: 13px;
}
</style>
