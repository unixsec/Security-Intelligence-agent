<!--
  安全情报分析智能体 — 报告管理页面
  版本：v1.0
  作者：alex (unix_sec@163.com)
-->
<template>
  <div class="reports-page">
    <div class="page-header">
      <h2>报告管理</h2>
    </div>

    <el-card shadow="never" class="filter-card">
      <el-row :gutter="12">
        <el-col :span="5">
          <el-select v-model="filters.report_type" placeholder="报告类型" clearable>
            <el-option label="日报" value="daily" />
            <el-option label="周报" value="weekly" />
            <el-option label="月报" value="monthly" />
            <el-option label="半年报" value="semi_annual" />
            <el-option label="年报" value="annual" />
          </el-select>
        </el-col>
        <el-col :span="5">
          <el-select v-model="filters.report_version" placeholder="版本" clearable>
            <el-option label="高管简版" value="executive" />
            <el-option label="安全运营详版" value="security_ops" />
          </el-select>
        </el-col>
        <el-col :span="5">
          <el-select v-model="filters.status" placeholder="状态" clearable>
            <el-option label="生成中" value="generating" />
            <el-option label="就绪" value="ready" />
            <el-option label="已推送" value="pushed" />
            <el-option label="错误" value="error" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-button type="primary" @click="loadReports">搜索</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-card shadow="never" class="mt-3">
      <el-table :data="reports" v-loading="loading" stripe>
        <el-table-column prop="report_code" label="报告编号" width="180" />
        <el-table-column prop="report_type" label="类型" width="90">
          <template #default="{ row }">
            <el-tag size="small">{{ typeLabel(row.report_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="report_version" label="版本" width="120">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ versionLabel(row.report_version) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="覆盖周期" width="210">
          <template #default="{ row }">
            {{ formatDate(row.period_start) }} ~ {{ formatDate(row.period_end) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="generated_at" label="生成时间" width="140">
          <template #default="{ row }">{{ formatDate(row.generated_at) }}</template>
        </el-table-column>
        <el-table-column prop="pushed_at" label="推送时间" width="140">
          <template #default="{ row }">{{ formatDate(row.pushed_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text @click="viewReport(row)">查看</el-button>
            <el-button size="small" text type="warning" @click="regenerate(row)">重新生成</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        class="mt-3"
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        @change="loadReports"
      />
    </el-card>

    <!-- 报告内容对话框 -->
    <el-dialog v-model="viewVisible" title="报告内容" width="820px" top="3vh">
      <div class="report-content" v-if="viewData">
        <pre>{{ viewData.content }}</pre>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { reportsApi } from '@/api'
import dayjs from 'dayjs'

const loading = ref(false), viewVisible = ref(false), viewData = ref(null)
const reports = ref([])
const filters = reactive({ report_type: '', report_version: '', status: '' })
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })

async function loadReports() {
  loading.value = true
  try {
    const res = await reportsApi.list({
      page: pagination.page, page_size: pagination.pageSize,
      ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)),
    })
    reports.value = res.items; pagination.total = res.total
  } finally { loading.value = false }
}

function resetFilters() { Object.assign(filters, { report_type: '', report_version: '', status: '' }); pagination.page = 1; loadReports() }

async function viewReport(row) { viewData.value = await reportsApi.get(row.id); viewVisible.value = true }

async function regenerate(row) {
  await ElMessageBox.confirm(`重新生成报告「${row.report_code}」？`, '确认操作', { type: 'warning' })
  await reportsApi.regenerate(row.id); ElMessage.success('重新生成任务已提交')
}

const typeLabel = (t) => ({ daily: '日报', weekly: '周报', monthly: '月报', semi_annual: '半年报', annual: '年报' }[t] || t)
const versionLabel = (v) => ({ executive: '高管简版', security_ops: '安全运营详版' }[v] || v)
const statusType = (s) => ({ generating: 'warning', ready: 'success', pushed: '', error: 'danger' }[s] || 'info')
const statusLabel = (s) => ({ generating: '生成中', ready: '就绪', pushed: '已推送', error: '错误' }[s] || s)
const formatDate = (d) => d ? dayjs(d).format('YYYY-MM-DD HH:mm') : '-'

onMounted(loadReports)
</script>

<style scoped>
.reports-page { max-width: 1400px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { font-size: 18px; font-weight: 600; color: #303133; }
.filter-card { margin-bottom: 0; }
.mt-3 { margin-top: 12px; }
.report-content { max-height: 70vh; overflow-y: auto; }
.report-content pre { white-space: pre-wrap; font-size: 13px; line-height: 1.7; color: #303133; font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; }
</style>
