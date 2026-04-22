<template>
  <div>
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center">
          <span>情报源管理</span>
          <el-button type="primary" @click="showAddDialog = true">
            <el-icon><Plus /></el-icon> 添加源
          </el-button>
        </div>
      </template>

      <el-table :data="sources" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="名称" min-width="200" />
        <el-table-column prop="source_type" label="类型" width="100" />
        <el-table-column prop="url" label="URL" show-overflow-tooltip min-width="300" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '运行中' : '已暂停' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="error_count" label="错误数" width="80" />
        <el-table-column label="上次采集" width="170">
          <template #default="{ row }">
            {{ row.last_fetched_at ? formatTime(row.last_fetched_at) : '从未' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleToggle(row)">
              {{ row.status === 'active' ? '暂停' : '启用' }}
            </el-button>
            <el-button size="small" type="primary" @click="handleCollect(row)" :loading="collectingId === row.id">
              立即采集
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Add Source Dialog -->
    <el-dialog v-model="showAddDialog" title="添加情报源" width="500px">
      <el-form :model="newSource" label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="newSource.name" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="newSource.source_type" style="width: 100%">
            <el-option label="RSS" value="rss" />
            <el-option label="API" value="api" />
            <el-option label="网页爬取" value="web_crawl" />
          </el-select>
        </el-form-item>
        <el-form-item label="URL" required>
          <el-input v-model="newSource.url" />
        </el-form-item>
        <el-form-item label="语言">
          <el-select v-model="newSource.language" style="width: 100%">
            <el-option label="英文" value="en" />
            <el-option label="中文" value="zh" />
            <el-option label="双语" value="both" />
          </el-select>
        </el-form-item>
        <el-form-item label="采集间隔">
          <el-input-number v-model="newSource.fetch_interval" :min="10" :max="1440" />
          <span style="margin-left: 8px; color: #999">分钟</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="handleAdd" :loading="adding">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { getSourceList, createSource, toggleSource, triggerCollection } from '../api'

const loading = ref(false)
const sources = ref([])
const showAddDialog = ref(false)
const adding = ref(false)
const collectingId = ref(null)

const newSource = reactive({
  name: '',
  source_type: 'rss',
  url: '',
  language: 'en',
  fetch_interval: 240,
})

const loadSources = async () => {
  loading.value = true
  try {
    sources.value = await getSourceList()
  } finally {
    loading.value = false
  }
}

const handleAdd = async () => {
  adding.value = true
  try {
    await createSource(newSource)
    showAddDialog.value = false
    ElMessage.success('添加成功')
    await loadSources()
  } catch {
    ElMessage.error('添加失败')
  } finally {
    adding.value = false
  }
}

const handleToggle = async (row) => {
  try {
    await toggleSource(row.id)
    await loadSources()
  } catch {
    ElMessage.error('操作失败')
  }
}

const handleCollect = async (row) => {
  collectingId.value = row.id
  try {
    const result = await triggerCollection(row.id)
    ElMessage.success(`采集完成：${result.collected} 条新情报`)
    await loadSources()
  } catch {
    ElMessage.error('采集失败')
  } finally {
    collectingId.value = null
  }
}

const formatTime = (t) => dayjs(t).format('YYYY-MM-DD HH:mm')

onMounted(loadSources)
</script>
