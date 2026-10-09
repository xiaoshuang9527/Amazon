<template>
  <el-dialog
    :model-value="modelValue"
    title="回填确认：当前文案 vs 生成文案"
    width="1080px"
    top="6vh"
    :close-on-click-modal="false"
    @update:model-value="handleVisible"
    @open="load"
  >
    <div v-loading="loading" class="diff-body">
      <el-alert v-if="info" type="info" :closable="false" show-icon class="meta">
        <template #title>
          站点 {{ info.marketplace_id }}（{{ info.target_language || '目标语言' }}）· 当前文案来源：{{
            sourceLabel
          }}
          · 模型：{{ info.model_used || '-' }}
        </template>
      </el-alert>

      <el-alert
        v-if="blockedViolations.length"
        type="error"
        :closable="false"
        show-icon
        class="meta"
        title="回填内容未通过合规校验，请修正后重试，或选择强制回填"
      >
        <ul class="violations">
          <li v-for="(item, index) in blockedViolations" :key="index">
            <el-tag type="danger" size="small">{{ item.type }}</el-tag>
            <span class="word">{{ item.word || item.field }}</span>
            <span class="suggestion">{{ item.suggestion || item.message }}</span>
          </li>
        </ul>
      </el-alert>

      <el-table :data="rows" border size="small" class="diff-table">
        <el-table-column width="52" align="center">
          <template #header>
            <el-checkbox
              :model-value="allSelected"
              :indeterminate="indeterminate"
              @change="toggleAll"
            />
          </template>
          <template #default="{ row }">
            <el-checkbox v-model="row.selected" />
          </template>
        </el-table-column>

        <el-table-column label="字段" width="96">
          <template #default="{ row }">
            <div class="field-name">{{ row.label }}</div>
            <el-tag v-if="row.changed" type="warning" size="small">有差异</el-tag>
            <el-tag v-else type="info" size="small">一致</el-tag>
          </template>
        </el-table-column>

        <el-table-column label="当前文案（将被替换部分标红）">
          <template #default="{ row }">
            <div class="diff-box" v-html="leftHtml(row)"></div>
          </template>
        </el-table-column>

        <el-table-column label="生成文案（新增内容标绿，可微调）">
          <template #default="{ row }">
            <el-input
              v-if="row.editing"
              v-model="row.edited"
              type="textarea"
              :autosize="{ minRows: 3, maxRows: 12 }"
            />
            <div v-else class="diff-box" v-html="rightHtml(row)"></div>
          </template>
        </el-table-column>

        <el-table-column width="76" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="row.editing = !row.editing">
              {{ row.editing ? '完成' : '微调' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="footer-tip">
        共 {{ rows.length }} 个字段，其中 {{ changedCount }} 个存在差异；已勾选
        {{ selectedCount }} 个将提交回填，未勾选字段保持当前文案不变。
      </div>
    </div>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button
        v-if="blockedViolations.length"
        type="warning"
        :loading="submitting"
        @click="submit(true)"
      >
        强制回填
      </el-button>
      <el-button type="primary" :loading="submitting" @click="submit(false)">确认回填</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { errorMessage, errorPayload, listingsApi } from '../api'
import { diffHtml, fieldToText, textToFieldValue } from '../utils/diff'
import type { ApplyResponse, BackfillField, ListingDiff, Violation } from '../types'

interface DiffRow {
  field: BackfillField
  label: string
  current: string
  proposed: string
  edited: string
  changed: boolean
  selected: boolean
  editing: boolean
}

const props = defineProps<{
  modelValue: boolean
  listingId: number | null
  taskId: string
  marketplace: string
  seed?: Record<string, any> | null
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
  (event: 'applied', payload: ApplyResponse): void
}>()

const loading = ref(false)
const submitting = ref(false)
const rows = ref<DiffRow[]>([])
const info = ref<ListingDiff | null>(null)
const blockedViolations = ref<Violation[]>([])

const sourceLabel = computed(() => {
  if (!info.value) return '-'
  return info.value.current_source === 'listing_copy' ? '上次回填结果' : 'Listing 原始信息'
})

const selectedCount = computed(() => rows.value.filter((row) => row.selected).length)
const changedCount = computed(() => rows.value.filter((row) => row.changed).length)
const allSelected = computed(
  () => rows.value.length > 0 && rows.value.every((row) => row.selected)
)
const indeterminate = computed(
  () => selectedCount.value > 0 && selectedCount.value < rows.value.length
)

function leftHtml(row: DiffRow): string {
  if (!row.current) return '<span class="diff-empty">（当前无内容）</span>'
  return diffHtml(row.current, row.edited).left
}

function rightHtml(row: DiffRow): string {
  if (!row.edited) return '<span class="diff-empty">（生成结果为空）</span>'
  return diffHtml(row.current, row.edited).right
}

function toggleAll(value: boolean | string | number) {
  const checked = Boolean(value)
  rows.value.forEach((row) => {
    row.selected = checked
  })
}

async function load() {
  blockedViolations.value = []
  if (!props.listingId || !props.taskId || !props.marketplace) return
  loading.value = true
  try {
    const diff = await listingsApi.diff(props.listingId, props.taskId, props.marketplace)
    info.value = diff
    rows.value = diff.fields.map((field) => {
      const current = fieldToText(field.current)
      const proposed = fieldToText(field.proposed)
      const seeded =
        props.seed && props.seed[field.field] !== undefined
          ? fieldToText(props.seed[field.field])
          : proposed
      const edited = seeded === '' ? proposed : seeded
      const changed = current !== edited
      return {
        field: field.field as BackfillField,
        label: field.label,
        current,
        proposed,
        edited,
        changed,
        selected: changed,
        editing: false
      }
    })
  } catch (error) {
    ElMessage.error(errorMessage(error, '获取文案差异失败'))
  } finally {
    loading.value = false
  }
}

async function submit(force: boolean) {
  if (!props.listingId) {
    ElMessage.warning('缺少 Listing，无法回填')
    return
  }
  if (!selectedCount.value) {
    ElMessage.warning('请至少勾选一个需要回填的字段')
    return
  }
  submitting.value = true
  try {
    const response = await listingsApi.apply(props.listingId, {
      task_id: props.taskId,
      marketplace_id: props.marketplace,
      force,
      selections: rows.value.map((row) => ({
        field: row.field,
        selected: row.selected,
        value: row.edited === row.proposed ? null : textToFieldValue(row.field, row.edited)
      }))
    })
    ElMessage.success(response.message || `已回填 ${response.applied_fields.length} 个字段`)
    emit('applied', response)
    close()
  } catch (error) {
    const payload = errorPayload(error)
    if (payload?.code === 'compliance_failed') {
      blockedViolations.value = payload?.details?.violations || []
      ElMessage.warning(payload?.message || '回填内容未通过合规校验')
    } else {
      ElMessage.error(errorMessage(error, '回填失败'))
    }
  } finally {
    submitting.value = false
  }
}

function close() {
  blockedViolations.value = []
  emit('update:modelValue', false)
}

function handleVisible(value: boolean) {
  if (!value) close()
}

defineExpose({ load })
</script>

<style scoped>
.diff-body {
  min-height: 240px;
}

.meta {
  margin-bottom: 12px;
}

.violations {
  padding-left: 18px;
  margin: 6px 0 0;
  font-size: 13px;
}

.violations li {
  margin-bottom: 4px;
}

.violations .word {
  color: #f56c6c;
  margin: 0 8px;
}

.violations .suggestion {
  color: #909399;
}

.diff-table :deep(.cell) {
  vertical-align: top;
}

.field-name {
  font-weight: 600;
  margin-bottom: 4px;
}

.diff-box {
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 220px;
  overflow: auto;
  font-size: 13px;
  line-height: 1.7;
  color: #303133;
}

.diff-box :deep(.diff-del) {
  background-color: #ffe3e3;
  color: #c92a2a;
  border-radius: 2px;
}

.diff-box :deep(.diff-ins) {
  background-color: #e6ffec;
  color: #1a7f37;
  border-radius: 2px;
}

.diff-box :deep(.diff-empty) {
  color: #c0c4cc;
}

.footer-tip {
  margin-top: 12px;
  font-size: 13px;
  color: #909399;
}
</style>
