<!--
  安全情报分析智能体 — 审计日志页面
  版本：v1.0
  作者：alex (unix_sec@163.com)
-->
<template>
  <div class="audit-page">
    <div class="page-header"><h2>审计日志</h2></div>
    <el-card shadow="never">
      <el-row :gutter="12" class="mb-3">
        <el-col :span="4">
          <el-select v-model="filters.action" placeholder="操作类型" clearable>
            <el-option label="创建" value="CREATE" />
            <el-option label="更新" value="UPDATE" />
            <el-option label="删除" value="DELETE" />
            <el-option label="导入" value="IMPORT" />
            <el-option label="导出" value="EXPORT" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-input v-model="filters.operator" placeholder="操作人" clearable />
        </el-col>
        <el-col :span="6">
          <el-date-picker v-model="dateRange" type="daterange" range-separator="至"
            start-placeholder="开始日期" end-placeholder="结束日期"
            value-format="YYYY-MM-DD" size="default" />
        </el-col>
        <el-col :span="4">
          <el-button type="primary" @click="loadLogs">搜索</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-col>
      </el-row>

      <el-table :data="logs" v-loading="loading" stripe>
        <el-table-column prop="action" label="操作" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="actionType(row.action)" size="small">{{ row.action }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="target_table" label="操作对象" width="150" />
        <el-table-column prop="target_id" label="对象ID" width="90" align="center" />
        <el-table-column prop="operator" label="操作人" width="130" />
        <el-table-column prop="created_at" label="时间" width="150">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text @click="viewDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination class="mt-3" v-model:current-page="pagination.page" v-model:page-size="pagination.pageSize"
        :total="pagination.total" layout="total, sizes, prev, pager, next" @change="loadLogs" />
    </el-card>

    <el-dialog v-model="detailVisible" title="变更详情" width="640px">
      <div v-if="detailRow">
        <el-row :gutter="12">
          <el-col :span="12" v-if="detailRow.old_value">
            <div class="diff-label">变更前</div>
            <pre class="diff-content">{{ JSON.stringify(detailRow.old_value, null, 2) }}</pre>
          </el-col>
          <el-col :span="12" v-if="detailRow.new_value">
            <div class="diff-label">变更后</div>
            <pre class="diff-content">{{ JSON.stringify(detailRow.new_value, null, 2) }}</pre>
          </el-col>
        </el-row>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { auditApi } from '@/api'
import dayjs from 'dayjs'

const loading = ref(false), detailVisible = ref(false), detailRow = ref(null)
const logs = ref([]), dateRange = ref([])
const filters = reactive({ action: '', operator: '' })
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })

async function loadLogs() {
  loading.value = true
  try {
    const params = { page: pagination.page, page_size: pagination.pageSize,
      ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) }
    if (dateRange.value?.length === 2) { params.date_from = dateRange.value[0]; params.date_to = dateRange.value[1] }
    const res = await auditApi.list(params); logs.value = res.items; pagination.total = res.total
  } finally { loading.value = false }
}

function resetFilters() { Object.assign(filters, { action: '', operator: '' }); dateRange.value = []; pagination.page = 1; loadLogs() }
function viewDetail(row) { detailRow.value = row; detailVisible.value = true }

const actionType = (a) => ({ CREATE: 'success', UPDATE: 'warning', DELETE: 'danger', IMPORT: 'info', EXPORT: '' }[a] || 'info')
const formatDate = (d) => d ? dayjs(d).format('YYYY-MM-DD HH:mm:ss') : '-'

onMounted(loadLogs)
</script>

<style scoped>
.audit-page { max-width: 1400px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { font-size: 18px; font-weight: 600; color: #303133; }
.mb-3 { margin-bottom: 12px; }
.mt-3 { margin-top: 12px; }
.diff-label { font-size: 13px; font-weight: 600; color: #606266; margin-bottom: 6px; }
.diff-content { background: #f5f7fa; padding: 12px; border-radius: 6px; font-size: 12px; overflow-x: auto; white-space: pre-wrap; }
</style>
