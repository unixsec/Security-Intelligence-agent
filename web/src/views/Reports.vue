<template>
  <div>
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>报告管理</span>
          <el-button type="primary" @click="showGenerateDialog = true">
            <el-icon><DocumentAdd /></el-icon> 生成报告
          </el-button>
        </div>
      </template>

      <el-table :data="reports" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="title" label="标题" min-width="300" />
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ typeLabel(row.report_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="P0" width="60">
          <template #default="{ row }">
            <span :style="{ color: row.p0_count > 0 ? '#F56C6C' : '#999' }">{{ row.p0_count }}</span>
          </template>
        </el-table-column>
        <el-table-column label="P1" width="60">
          <template #default="{ row }">
            <span :style="{ color: row.p1_count > 0 ? '#E6A23C' : '#999' }">{{ row.p1_count }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'pushed' ? 'success' : ''" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="生成时间" width="170">
          <template #default="{ row }">{{ formatTime(row.generated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button size="small" @click="viewReport(row.id)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Generate Dialog -->
    <el-dialog v-model="showGenerateDialog" title="生成报告" width="400px">
      <el-form :model="genForm" label-width="80px">
        <el-form-item label="报告类型">
          <el-select v-model="genForm.report_type" style="width: 100%">
            <el-option label="日报" value="daily" />
            <el-option label="周报" value="weekly" />
            <el-option label="月报" value="monthly" />
            <el-option label="紧急报告" value="emergency" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标受众">
          <el-select v-model="genForm.audience" style="width: 100%">
            <el-option label="管理层" value="executive" />
            <el-option label="运营团队" value="operational" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showGenerateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleGenerate" :loading="generating">生成</el-button>
      </template>
    </el-dialog>

    <!-- Report Detail Dialog -->
    <el-dialog v-model="showDetailDialog" title="报告详情" width="800px">
      <div v-if="currentReport">
        <h3>{{ currentReport.title }}</h3>
        <el-descriptions :column="2" border style="margin: 16px 0">
          <el-descriptions-item label="类型">{{ typeLabel(currentReport.report_type) }}</el-descriptions-item>
          <el-descriptions-item label="时间段">
            {{ formatTime(currentReport.period_start) }} — {{ formatTime(currentReport.period_end) }}
          </el-descriptions-item>
          <el-descriptions-item label="情报总数">{{ currentReport.stats?.intel_total }}</el-descriptions-item>
          <el-descriptions-item label="入选数">{{ currentReport.stats?.intel_selected }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="currentReport.content" class="report-content">
          <pre>{{ JSON.stringify(currentReport.content, null, 2) }}</pre>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { getReportList, getReportDetail, generateReport } from '../api'

const loading = ref(false)
const generating = ref(false)
const reports = ref([])
const showGenerateDialog = ref(false)
const showDetailDialog = ref(false)
const currentReport = ref(null)

const genForm = reactive({
  report_type: 'daily',
  audience: 'executive',
})

const typeLabel = (t) => ({ daily: '日报', weekly: '周报', monthly: '月报', emergency: '紧急', quarterly: '季报' }[t] || t)
const statusLabel = (s) => ({ generating: '生成中', generated: '已生成', pushing: '推送中', pushed: '已推送', failed: '失败' }[s] || s)
const formatTime = (t) => t ? dayjs(t).format('YYYY-MM-DD HH:mm') : '-'

const loadReports = async () => {
  loading.value = true
  try {
    reports.value = await getReportList()
  } finally {
    loading.value = false
  }
}

const handleGenerate = async () => {
  generating.value = true
  try {
    await generateReport(genForm)
    showGenerateDialog.value = false
    ElMessage.success('报告生成成功')
    await loadReports()
  } catch {
    ElMessage.error('报告生成失败')
  } finally {
    generating.value = false
  }
}

const viewReport = async (id) => {
  try {
    currentReport.value = await getReportDetail(id)
    showDetailDialog.value = true
  } catch {
    ElMessage.error('加载报告失败')
  }
}

onMounted(loadReports)
</script>

<style scoped>
.report-content {
  max-height: 400px;
  overflow-y: auto;
  background: #f5f7fa;
  padding: 16px;
  border-radius: 4px;
}
.report-content pre {
  white-space: pre-wrap;
  font-size: 13px;
}
</style>
