<template>
  <div>
    <!-- Filters -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters">
        <el-form-item label="优先级">
          <el-select v-model="filters.priority" clearable placeholder="全部" style="width: 100px">
            <el-option v-for="p in ['P0','P1','P2','P3']" :key="p" :label="p" :value="p" />
          </el-select>
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="filters.category" clearable placeholder="全部" style="width: 140px">
            <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="全部" style="width: 120px">
            <el-option label="待处理" value="raw" />
            <el-option label="已分析" value="analyzed" />
            <el-option label="已发布" value="published" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" placeholder="搜索标题/内容" clearable style="width: 200px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">搜索</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Table -->
    <el-card style="margin-top: 16px">
      <el-table :data="items" v-loading="loading" stripe @row-click="goDetail">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="优先级" width="80">
          <template #default="{ row }">
            <el-tag :type="priorityTagType(row.priority_level)" size="small">
              {{ row.priority_level }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" show-overflow-tooltip min-width="300" />
        <el-table-column prop="primary_category" label="分类" width="120" />
        <el-table-column label="评分" width="80">
          <template #default="{ row }">
            {{ row.total_score ? row.total_score.toFixed(1) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="source_name" label="来源" width="120" />
        <el-table-column prop="cve_id" label="CVE" width="140" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.processing_status)" size="small">
              {{ statusLabel(row.processing_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="采集时间" width="170">
          <template #default="{ row }">{{ formatTime(row.collected_at) }}</template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        style="margin-top: 16px; justify-content: flex-end"
        @current-change="loadData"
        @size-change="loadData"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { getIntelligenceList } from '../api'

const router = useRouter()
const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const filters = reactive({
  priority: '',
  category: '',
  status: '',
  keyword: '',
})

const categories = [
  'vulnerability', 'threat_actor', 'malware', 'data_breach',
  'supply_chain', 'regulatory', 'apt', 'zero_day', 'ransomware',
]

const loadData = async () => {
  loading.value = true
  try {
    const data = await getIntelligenceList({
      page: page.value,
      page_size: pageSize.value,
      ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)),
    })
    items.value = data.items
    total.value = data.total
  } catch (e) {
    console.error('Failed to load intelligence:', e)
  } finally {
    loading.value = false
  }
}

const goDetail = (row) => router.push(`/intelligence/${row.id}`)

const priorityTagType = (p) => ({ P0: 'danger', P1: 'warning', P2: '', P3: 'info' }[p] || '')
const statusTagType = (s) => ({ raw: 'info', analyzed: 'success', published: '' }[s] || 'info')
const statusLabel = (s) => ({ raw: '待处理', preprocessed: '预处理', analyzed: '已分析', published: '已发布', archived: '已归档' }[s] || s)
const formatTime = (t) => t ? dayjs(t).format('YYYY-MM-DD HH:mm') : '-'

onMounted(loadData)
</script>

<style scoped>
.filter-card { margin-bottom: 0; }
.el-table { cursor: pointer; }
</style>
