<!--
  安全情报分析智能体 — 情报列表页面
  版本：v1.0
  作者：alex (unix_sec@163.com)
-->
<template>
  <div class="intel-page">
    <div class="page-header">
      <h2>情报列表</h2>
      <el-radio-group v-model="activeTab" size="small">
        <el-radio-button value="scored">已评分情报</el-radio-button>
        <el-radio-button value="raw">原始情报</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 筛选栏 -->
    <el-card shadow="never" class="filter-card">
      <el-row :gutter="12">
        <template v-if="activeTab === 'scored'">
          <el-col :span="4">
            <el-select v-model="scoredFilters.p_level" placeholder="P级别" clearable>
              <el-option label="P0 紧急" value="P0" />
              <el-option label="P1 重要" value="P1" />
              <el-option label="P2 普通" value="P2" />
            </el-select>
          </el-col>
          <el-col :span="4">
            <el-select v-model="scoredFilters.intel_type" placeholder="情报类型" clearable>
              <el-option v-for="t in intelTypes" :key="t.value" :label="t.label" :value="t.value" />
            </el-select>
          </el-col>
          <el-col :span="4">
            <el-select v-model="scoredFilters.severity" placeholder="严重程度" clearable>
              <el-option label="高危" value="high" />
              <el-option label="中危" value="medium" />
              <el-option label="低危" value="low" />
            </el-select>
          </el-col>
          <el-col :span="6">
            <el-date-picker
              v-model="scoredDateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              size="default"
            />
          </el-col>
        </template>
        <el-col :span="4">
          <el-button type="primary" @click="loadData">搜索</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 已评分情报表格 -->
    <el-card shadow="never" class="mt-3" v-if="activeTab === 'scored'">
      <el-table :data="intelList" v-loading="loading" stripe @row-click="openDetail">
        <el-table-column prop="p_level" label="P级" width="70" align="center">
          <template #default="{ row }">
            <el-tag :type="pLevelType(row.p_level)" size="small" effect="dark">{{ row.p_level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_score" label="综合分" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="scoreType(row.total_score)" size="small">{{ row.total_score }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="情报标题" min-width="260" show-overflow-tooltip />
        <el-table-column prop="intel_type" label="类型" width="100">
          <template #default="{ row }">{{ intelTypeLabel(row.intel_type) }}</template>
        </el-table-column>
        <el-table-column prop="severity" label="严重度" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="severityType(row.severity)" size="small">{{ severityLabel(row.severity) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="cve_id" label="CVE" width="140" />
        <el-table-column prop="is_pushed" label="已推送" width="80" align="center">
          <template #default="{ row }">
            <el-icon :color="row.is_pushed ? '#67c23a' : '#c0c4cc'">
              <CircleCheck v-if="row.is_pushed" /><Minus v-else />
            </el-icon>
          </template>
        </el-table-column>
        <el-table-column prop="scored_at" label="评分时间" width="130">
          <template #default="{ row }">{{ formatDate(row.scored_at) }}</template>
        </el-table-column>
      </el-table>

      <el-pagination
        class="mt-3"
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        @change="loadData"
      />
    </el-card>

    <!-- 原始情报表格 -->
    <el-card shadow="never" class="mt-3" v-if="activeTab === 'raw'">
      <el-table :data="intelList" v-loading="loading" stripe>
        <el-table-column prop="source_name" label="来源" width="160" />
        <el-table-column prop="title" label="标题" min-width="300" show-overflow-tooltip />
        <el-table-column prop="language" label="语言" width="70" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.language }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="rawStatusType(row.status)" size="small">{{ rawStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="collected_at" label="采集时间" width="130">
          <template #default="{ row }">{{ formatDate(row.collected_at) }}</template>
        </el-table-column>
      </el-table>

      <el-pagination
        class="mt-3"
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        @change="loadData"
      />
    </el-card>

    <!-- 情报详情对话框 -->
    <el-dialog v-model="detailVisible" title="情报详情" width="760px" top="5vh">
      <div v-if="detailData" class="detail-content">
        <div class="detail-title">{{ detailData.title }}</div>
        <el-row :gutter="12" class="detail-tags">
          <el-col>
            <el-tag :type="pLevelType(detailData.p_level)" effect="dark">{{ detailData.p_level }}</el-tag>
            <el-tag :type="severityType(detailData.severity)">{{ severityLabel(detailData.severity) }}</el-tag>
            <el-tag type="info">{{ intelTypeLabel(detailData.intel_type) }}</el-tag>
            <el-tag v-if="detailData.cve_id" type="warning">{{ detailData.cve_id }}</el-tag>
          </el-col>
        </el-row>

        <el-descriptions :column="2" border size="small" class="mt-3">
          <el-descriptions-item label="综合分">{{ detailData.total_score }}</el-descriptions-item>
          <el-descriptions-item label="P级别">{{ detailData.p_level }}</el-descriptions-item>
          <el-descriptions-item label="威胁可能性">{{ detailData.score_threat }}</el-descriptions-item>
          <el-descriptions-item label="业务影响度">{{ detailData.score_business }}</el-descriptions-item>
          <el-descriptions-item label="合规影响度">{{ detailData.score_compliance }}</el-descriptions-item>
          <el-descriptions-item label="时效紧迫性">{{ detailData.score_urgency }}</el-descriptions-item>
          <el-descriptions-item label="情报质量">{{ detailData.score_quality }}</el-descriptions-item>
          <el-descriptions-item label="资产域">{{ detailData.asset_domain || '-' }}</el-descriptions-item>
          <el-descriptions-item label="影响市场" :span="2">
            {{ (detailData.affected_markets || []).join('、') || '-' }}
          </el-descriptions-item>
        </el-descriptions>

        <div class="detail-section" v-if="detailData.summary_zh">
          <div class="section-title">中文摘要</div>
          <p>{{ detailData.summary_zh }}</p>
        </div>
        <div class="detail-section" v-if="detailData.impact_analysis">
          <div class="section-title">影响分析</div>
          <p>{{ detailData.impact_analysis }}</p>
        </div>
        <div class="detail-section" v-if="detailData.recommendations?.length">
          <div class="section-title">处置建议</div>
          <ul><li v-for="r in detailData.recommendations" :key="r">{{ r }}</li></ul>
        </div>
        <div class="detail-section" v-if="detailData.ai_commentary">
          <div class="section-title">AI 专家点评</div>
          <p>{{ detailData.ai_commentary }}</p>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, watch, onMounted } from 'vue'
import { intelApi } from '@/api'
import dayjs from 'dayjs'

const loading = ref(false)
const activeTab = ref('scored')
const intelList = ref([])
const detailVisible = ref(false)
const detailData = ref(null)
const scoredDateRange = ref([])

const scoredFilters = reactive({ p_level: '', intel_type: '', severity: '' })
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })

const intelTypes = [
  { value: 'vulnerability', label: '漏洞' },
  { value: 'attack', label: '攻击事件' },
  { value: 'regulation', label: '法规' },
  { value: 'data_breach', label: '数据泄露' },
  { value: 'opinion', label: '观点' },
  { value: 'trend', label: '趋势' },
  { value: 'technology', label: '技术' },
  { value: 'industry', label: '行业动态' },
]

async function loadData() {
  loading.value = true
  try {
    let res
    if (activeTab.value === 'scored') {
      const params = {
        page: pagination.page,
        page_size: pagination.pageSize,
        ...Object.fromEntries(Object.entries(scoredFilters).filter(([, v]) => v)),
      }
      if (scoredDateRange.value?.length === 2) {
        params.date_from = scoredDateRange.value[0]
        params.date_to = scoredDateRange.value[1]
      }
      res = await intelApi.listScored(params)
    } else {
      res = await intelApi.listRaw({ page: pagination.page, page_size: pagination.pageSize })
    }
    intelList.value = res.items
    pagination.total = res.total
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  Object.assign(scoredFilters, { p_level: '', intel_type: '', severity: '' })
  scoredDateRange.value = []
  pagination.page = 1
  loadData()
}

async function openDetail(row) {
  if (activeTab.value !== 'scored') return
  detailData.value = await intelApi.getScored(row.id)
  detailVisible.value = true
}

watch(activeTab, () => {
  pagination.page = 1
  loadData()
})

const pLevelType = (p) => ({ P0: 'danger', P1: 'warning', P2: '' }[p] || '')
const scoreType = (s) => s >= 85 ? 'danger' : s >= 75 ? 'warning' : s >= 60 ? 'success' : 'info'
const severityType = (s) => ({ high: 'danger', medium: 'warning', low: 'info' }[s] || 'info')
const severityLabel = (s) => ({ high: '高危', medium: '中危', low: '低危' }[s] || s)
const intelTypeLabel = (t) => intelTypes.find(x => x.value === t)?.label || t
const rawStatusType = (s) => ({ pending: 'info', processing: 'warning', analyzed: 'success', duplicate: '', error: 'danger' }[s] || '')
const rawStatusLabel = (s) => ({ pending: '待处理', processing: '处理中', analyzed: '已分析', duplicate: '重复', error: '错误' }[s] || s)
const formatDate = (d) => d ? dayjs(d).format('MM-DD HH:mm') : '-'

onMounted(loadData)
</script>

<style scoped>
.intel-page { max-width: 1400px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { font-size: 18px; font-weight: 600; color: #303133; }
.filter-card { margin-bottom: 0; }
.mt-3 { margin-top: 12px; }
.detail-title { font-size: 16px; font-weight: 600; color: #303133; margin-bottom: 12px; line-height: 1.5; }
.detail-tags { margin-bottom: 0; }
.detail-tags .el-tag { margin-right: 8px; }
.detail-section { margin-top: 16px; }
.section-title { font-size: 14px; font-weight: 600; color: #303133; margin-bottom: 8px; border-left: 3px solid #409eff; padding-left: 8px; }
.detail-section p { color: #606266; line-height: 1.7; font-size: 14px; }
.detail-section ul { padding-left: 20px; color: #606266; font-size: 14px; }
.detail-section li { margin-bottom: 4px; line-height: 1.6; }
</style>
