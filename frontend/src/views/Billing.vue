<template>
  <div class="page">
    <el-row :gutter="16" style="margin-bottom: 16px">
      <el-col :span="12">
        <el-card>
          <template #header><span class="title">当前套餐</span></template>
          <div class="plan-name">{{ currentPlanName }}</div>
          <div class="plan-price">
            ¥{{ currentPlanPrice }}<span class="unit">/月</span>
          </div>
          <p class="desc">{{ currentPlanDesc }}</p>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header><span class="title">本月用量</span></template>
          <el-progress
            type="dashboard"
            :percentage="usagePercent"
            :color="usageColor"
          />
          <p class="usage-text">已用 {{ used }}/{{ total }} 条 Listing</p>
        </el-card>
      </el-col>
    </el-row>

    <el-card>
      <template #header><span class="title">套餐列表</span></template>
      <el-row :gutter="16">
        <el-col :span="8" v-for="plan in plans" :key="plan.code">
          <el-card :class="['plan-card', { active: plan.code === usage.plan }]">
            <h3>{{ plan.name }}</h3>
            <div class="price">¥{{ plan.price_monthly }}<span class="unit">/月</span></div>
            <div class="yearly">
              年付 ¥{{ plan.price_yearly }}（相当于 ¥{{ Math.round(plan.price_per_month_yearly) }}/月）
            </div>
            <p class="desc">每月 {{ plan.monthly_quota }} 条 Listing 生成</p>
            <el-button
              type="primary"
              style="width: 100%"
              :loading="subscribing === plan.code"
              :disabled="plan.code === usage.plan"
              @click="handleSubscribe(plan)"
            >
              {{ plan.code === usage.plan ? '当前套餐' : '升级 / 订阅' }}
            </el-button>
          </el-card>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { billingApi, errorMessage } from '../api'
import type { PlanRead, UsageRead } from '../types'

const plans = ref<PlanRead[]>([])
const subscribing = ref('')

const usage = reactive<UsageRead>({
  plan: 'free',
  status: 'active',
  quota_total: 0,
  quota_used: 0,
  quota_remaining: 0
})

const used = computed(() => usage.quota_used)
const total = computed(() => usage.quota_total)

const currentPlan = computed(() => plans.value.find((p) => p.code === usage.plan))
const currentPlanName = computed(() => currentPlan.value?.name || usage.plan)
const currentPlanPrice = computed(() => currentPlan.value?.price_monthly ?? 0)
const currentPlanDesc = computed(() =>
  currentPlan.value ? `每月 ${currentPlan.value.monthly_quota} 条 Listing 生成` : '—'
)

const usagePercent = computed(() => {
  if (!total.value) return 0
  return Math.min(100, Math.round((used.value / total.value) * 100))
})

const usageColor = computed(() => {
  const p = usagePercent.value
  if (p >= 90) return '#f56c6c'
  if (p >= 70) return '#e6a23c'
  return '#67c23a'
})

async function loadData() {
  try {
    const [planList, usageData] = await Promise.all([billingApi.plans(), billingApi.usage()])
    plans.value = planList
    Object.assign(usage, usageData)
  } catch (error) {
    ElMessage.error(errorMessage(error, '加载套餐信息失败'))
  }
}

const handleSubscribe = async (plan: PlanRead) => {
  subscribing.value = plan.code
  try {
    const result = await billingApi.subscribe(plan.code, 'monthly')
    ElMessage.success(`已开通 ${plan.name}，金额 ¥${result.amount}（MVP：直接开通，支付二期接入）`)
    Object.assign(usage, await billingApi.usage())
  } catch (error) {
    ElMessage.error(errorMessage(error, '开通套餐失败'))
  } finally {
    subscribing.value = ''
  }
}

onMounted(loadData)
</script>

<style scoped>
.page { padding: 8px; }
.title { font-weight: 600; }
.plan-name { font-size: 22px; font-weight: bold; color: #303133; }
.plan-price { font-size: 28px; color: #f56c6c; margin: 8px 0; }
.unit { font-size: 14px; color: #909399; }
.yearly { font-size: 13px; color: #67c23a; margin-left: 10px; }
.desc { color: #606266; font-size: 13px; }
.usage-text { text-align: center; color: #606266; margin-top: 8px; }
.plan-card { text-align: center; }
.plan-card.active { border: 2px solid #409eff; }
.plan-card h3 { margin: 8px 0; }
.price { font-size: 24px; color: #f56c6c; }
</style>
