<template>
  <div class="dashboard">
    <!-- Stats Cards -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="4" v-for="card in statCards" :key="card.label">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value" :style="{ color: card.color }">{{ card.value }}</div>
          <div class="stat-label">{{ card.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Charts -->
    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="12">
        <el-card header="情报分类分布">
          <v-chart :option="categoryChartOption" autoresize style="height: 350px" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card header="近7天优先级趋势">
          <v-chart :option="trendChartOption" autoresize style="height: 350px" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { PieChart, LineChart, BarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getDashboardStats, getCategoryDistribution, getPriorityTrend } from '../api'

use([PieChart, LineChart, BarChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent, CanvasRenderer])

const stats = ref({})
const categoryData = ref([])
const trendData = ref([])

const statCards = computed(() => [
  { label: '情报总量', value: stats.value.total_intel || 0, color: '#409EFF' },
  { label: '今日采集', value: stats.value.today_collected || 0, color: '#67C23A' },
  { label: '活跃 P0', value: stats.value.p0_active || 0, color: '#F56C6C' },
  { label: '活跃 P1', value: stats.value.p1_active || 0, color: '#E6A23C' },
  { label: '活跃事件', value: stats.value.active_events || 0, color: '#909399' },
  { label: '活跃源', value: stats.value.active_sources || 0, color: '#409EFF' },
])

const categoryChartOption = computed(() => ({
  tooltip: { trigger: 'item' },
  legend: { bottom: 0 },
  series: [{
    type: 'pie',
    radius: ['40%', '70%'],
    data: categoryData.value.map(c => ({ name: c.category, value: c.count })),
    emphasis: { itemStyle: { shadowBlur: 10 } },
  }],
}))

const trendChartOption = computed(() => {
  const dates = [...new Set(trendData.value.map(d => d.date))].sort()
  const priorities = ['P0', 'P1', 'P2', 'P3']
  const colors = { P0: '#F56C6C', P1: '#E6A23C', P2: '#409EFF', P3: '#909399' }

  return {
    tooltip: { trigger: 'axis' },
    legend: { data: priorities },
    grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value' },
    series: priorities.map(p => ({
      name: p,
      type: 'line',
      smooth: true,
      itemStyle: { color: colors[p] },
      data: dates.map(d => {
        const item = trendData.value.find(t => t.date === d && t.priority === p)
        return item ? item.count : 0
      }),
    })),
  }
})

onMounted(async () => {
  try {
    const [s, c, t] = await Promise.all([
      getDashboardStats(),
      getCategoryDistribution(),
      getPriorityTrend(7),
    ])
    stats.value = s
    categoryData.value = c
    trendData.value = t
  } catch (e) {
    console.error('Failed to load dashboard data:', e)
  }
})
</script>

<style scoped>
.stat-card {
  text-align: center;
  cursor: default;
}
.stat-value {
  font-size: 28px;
  font-weight: bold;
  margin-bottom: 4px;
}
.stat-label {
  font-size: 13px;
  color: #909399;
}
</style>
