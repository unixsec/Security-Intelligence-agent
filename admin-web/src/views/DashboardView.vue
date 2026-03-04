<!--
  安全情报分析智能体 — 系统概览仪表盘
  版本：v1.0
  作者：alex (unix_sec@163.com)
-->
<template>
  <div class="dashboard">
    <div class="page-header">
      <h2>系统概览</h2>
      <el-button @click="loadStats" :loading="loading" size="small" text>
        <el-icon><Refresh /></el-icon>刷新
      </el-button>
    </div>

    <!-- 核心指标卡片 -->
    <el-row :gutter="16" class="stat-cards">
      <el-col :span="6" v-for="card in statCards" :key="card.key">
        <el-card shadow="never" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" :style="{ background: card.bg }">
              <el-icon :size="24" :color="card.color">
                <component :is="card.icon" />
              </el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats[card.key] ?? '-' }}</div>
              <div class="stat-label">{{ card.label }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 系统健康状态 -->
    <el-row :gutter="16" class="mt-4">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <span>系统健康状态</span>
          </template>
          <el-descriptions :column="1" border size="small" v-if="health">
            <el-descriptions-item label="整体状态">
              <el-tag :type="healthTagType(health.status)">
                {{ healthLabel(health.status) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="数据库">
              <el-tag :type="health.database ? 'success' : 'danger'">
                {{ health.database ? '正常' : '异常' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="Dify API">
              <el-tag :type="health.dify_api ? 'success' : 'danger'">
                {{ health.dify_api ? '正常' : '异常' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="情报源可用率">
              <el-progress
                :percentage="Math.round((health.active_sources_ratio || 0) * 100)"
                :status="health.active_sources_ratio >= 0.8 ? 'success' : 'warning'"
                :stroke-width="10"
              />
            </el-descriptions-item>
          </el-descriptions>
          <el-skeleton v-else :rows="4" animated />
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <span>读者反馈汇总（近30天）</span>
          </template>
          <el-descriptions :column="1" border size="small" v-if="feedbacks">
            <el-descriptions-item label="总反馈数">{{ feedbacks.total_feedbacks }}</el-descriptions-item>
            <el-descriptions-item label="有价值">
              <el-text type="success">{{ feedbacks.valuable }}</el-text>
            </el-descriptions-item>
            <el-descriptions-item label="需改进">
              <el-text type="warning">{{ feedbacks.not_valuable }}</el-text>
            </el-descriptions-item>
            <el-descriptions-item label="满意率">
              <el-tag type="success">{{ feedbacks.satisfaction_rate }}</el-tag>
            </el-descriptions-item>
          </el-descriptions>
          <el-skeleton v-else :rows="4" animated />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { dashboardApi } from '@/api'

const loading = ref(false)
const stats = ref({})
const health = ref(null)
const feedbacks = ref(null)

const statCards = [
  { key: 'today_raw_intel', label: '今日采集情报', icon: 'Download', color: '#409eff', bg: '#ecf5ff' },
  { key: 'today_scored_intel', label: '今日分析情报', icon: 'Cpu', color: '#67c23a', bg: '#f0f9eb' },
  { key: 'today_p0_alerts', label: '今日P0紧急', icon: 'Warning', color: '#f56c6c', bg: '#fef0f0' },
  { key: 'today_p1_alerts', label: '今日P1重要', icon: 'Bell', color: '#e6a23c', bg: '#fdf6ec' },
  { key: 'total_sources', label: '情报源总数', icon: 'Connection', color: '#909399', bg: '#f4f4f5' },
  { key: 'active_sources', label: '活跃情报源', icon: 'CircleCheck', color: '#67c23a', bg: '#f0f9eb' },
  { key: 'error_sources', label: '异常情报源', icon: 'CircleClose', color: '#f56c6c', bg: '#fef0f0' },
  { key: 'today_reports', label: '今日报告', icon: 'Memo', color: '#409eff', bg: '#ecf5ff' },
]

function healthTagType(status) {
  return { healthy: 'success', degraded: 'warning', critical: 'danger' }[status] || 'info'
}
function healthLabel(status) {
  return { healthy: '健康', degraded: '部分降级', critical: '严重异常' }[status] || '未知'
}

async function loadStats() {
  loading.value = true
  try {
    const [statsData, healthData, feedbackData] = await Promise.all([
      dashboardApi.stats(),
      dashboardApi.health(),
      dashboardApi.feedbacks(),
    ])
    stats.value = statsData
    health.value = healthData
    feedbacks.value = feedbackData
  } finally {
    loading.value = false
  }
}

onMounted(loadStats)
</script>

<style scoped>
.dashboard { max-width: 1400px; }
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.page-header h2 { font-size: 18px; font-weight: 600; color: #303133; }
.stat-cards { margin-bottom: 0; }
.stat-card { border-radius: 8px; }
.stat-content {
  display: flex;
  align-items: center;
  gap: 16px;
}
.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.stat-value { font-size: 28px; font-weight: 700; color: #303133; line-height: 1; }
.stat-label { font-size: 13px; color: #909399; margin-top: 4px; }
.mt-4 { margin-top: 16px; }
</style>
