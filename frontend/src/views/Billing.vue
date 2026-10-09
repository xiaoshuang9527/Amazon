<template>
  <div class="page">
    <el-row :gutter="16" style="margin-bottom: 16px">
      <el-col :span="12">
        <el-card>
          <template #header><span class="title">当前套餐</span></template>
          <div class="plan-name">{{ currentPlan.name }}</div>
          <div class="plan-price">
            ¥{{ currentPlan.price }}<span class="unit">/月</span>
            <span v-if="currentPlan.yearly" class="yearly">相当于 ¥{{ Math.round(currentPlan.yearly / 12) }}/月</span>
          </div>
          <p class="desc">{{ currentPlan.desc }}</p>
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
        <el-col :span="8" v-for="plan in plans" :key="plan.key">
          <el-card :class="['plan-card', { active: plan.key === currentPlan.key }]">
            <h3>{{ plan.name }}</h3>
            <div class="price">¥{{ plan.price }}<span class="unit">/月</span></div>
            <div class="yearly">年付 ¥{{ plan.yearly }}（相当于 ¥{{ Math.round(plan.yearly / 12) }}/月）</div>
            <p class="desc">{{ plan.desc }}</p>
            <el-button
              type="primary"
              style="width: 100%"
              :disabled="plan.key === currentPlan.key"
              @click="handleSubscribe(plan)"
            >
              {{ plan.key === currentPlan.key ? '当前套餐' : '升级 / 订阅' }}
            </el-button>
          </el-card>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'

const plans = [
  { key: 'free', name: '免费版', price: 0, yearly: 0, desc: '每月 3 条 Listing 生成，基础导出' },
  { key: 'basic', name: '基础版', price: 199, yearly: 1999, desc: '50 条/月，单店铺' },
  { key: 'pro', name: '专业版', price: 399, yearly: 3999, desc: '200 条/月，多店铺，高质量模型' }
]

const currentPlan = ref(plans[0])
const used = ref(0)
const total = ref(3)

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

const handleSubscribe = (plan: any) => {
  ElMessage.info(`正在创建订单：${plan.name}（MVP 阶段支持管理员手动开通）`)
  // TODO: 调用 POST /billing/subscribe 创建订单
}
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