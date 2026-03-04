<!--
  安全情报分析智能体 — 情报源管理页面
  版本：v1.0
  作者：alex (unix_sec@163.com)
-->
<template>
  <div class="sources-page">
    <div class="page-header">
      <h2>情报源管理</h2>
      <div class="actions">
        <el-button @click="showImport = true" plain>
          <el-icon><Upload /></el-icon>批量导入
        </el-button>
        <el-button @click="handleExport" plain>
          <el-icon><Download /></el-icon>导出
        </el-button>
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon>新增情报源
        </el-button>
      </div>
    </div>

    <!-- 筛选栏 -->
    <el-card shadow="never" class="filter-card">
      <el-row :gutter="12">
        <el-col :span="5">
          <el-select v-model="filters.source_type" placeholder="类型" clearable>
            <el-option label="RSS" value="rss" />
            <el-option label="网页" value="website" />
            <el-option label="微信公众号" value="wechat" />
            <el-option label="搜索关键词" value="search_keyword" />
          </el-select>
        </el-col>
        <el-col :span="5">
          <el-select v-model="filters.status" placeholder="状态" clearable>
            <el-option label="活跃" value="active" />
            <el-option label="暂停" value="paused" />
            <el-option label="异常" value="error" />
          </el-select>
        </el-col>
        <el-col :span="5">
          <el-select v-model="filters.category" placeholder="分类" clearable>
            <el-option label="通用安全" value="general_security" />
            <el-option label="企业IT" value="enterprise_it" />
            <el-option label="车联网" value="automotive" />
            <el-option label="合规" value="compliance" />
            <el-option label="供应链" value="supply_chain" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-button type="primary" @click="loadSources">搜索</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-col>
      </el-row>
    </el-card>

    <!-- 数据表格 -->
    <el-card shadow="never" class="mt-3">
      <el-table :data="sources" v-loading="loading" stripe>
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column prop="source_type" label="类型" width="110">
          <template #default="{ row }">
            <el-tag size="small">{{ typeLabel(row.source_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="分类" width="110">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ categoryLabel(row.category) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="priorityType(row.priority)" size="small">{{ row.priority }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="health_score" label="健康分" width="100" align="center">
          <template #default="{ row }">
            <el-progress
              :percentage="row.health_score"
              :status="row.health_score >= 80 ? 'success' : row.health_score >= 50 ? 'warning' : 'exception'"
              :stroke-width="8"
            />
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_success_at" label="最后成功" width="160">
          <template #default="{ row }">{{ formatDate(row.last_success_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text @click="openEdit(row)">编辑</el-button>
            <el-button size="small" text type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        class="mt-3"
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next"
        :page-sizes="[20, 50, 100]"
        @change="loadSources"
      />
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingRow ? '编辑情报源' : '新增情报源'"
      width="560px"
    >
      <el-form :model="form" label-width="90px" :rules="rules" ref="formRef">
        <el-form-item label="类型" prop="source_type">
          <el-select v-model="form.source_type">
            <el-option label="RSS" value="rss" />
            <el-option label="网页" value="website" />
            <el-option label="微信公众号" value="wechat" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="URL" prop="url">
          <el-input v-model="form.url" />
        </el-form-item>
        <el-form-item label="分类" prop="category">
          <el-select v-model="form.category">
            <el-option label="通用安全" value="general_security" />
            <el-option label="企业IT" value="enterprise_it" />
            <el-option label="车联网" value="automotive" />
            <el-option label="合规" value="compliance" />
            <el-option label="供应链" value="supply_chain" />
          </el-select>
        </el-form-item>
        <el-form-item label="语言">
          <el-radio-group v-model="form.language">
            <el-radio value="zh">中文</el-radio>
            <el-radio value="en">英文</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="优先级">
          <el-radio-group v-model="form.priority">
            <el-radio value="high">高</el-radio>
            <el-radio value="medium">中</el-radio>
            <el-radio value="low">低</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.notes" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- 导入对话框 -->
    <el-dialog v-model="showImport" title="批量导入情报源" width="400px">
      <el-upload
        drag
        :auto-upload="false"
        accept=".csv"
        :on-change="handleImportFile"
        :limit="1"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">拖拽 CSV 文件到此处，或 <em>点击上传</em></div>
        <template #tip>
          <div class="el-upload__tip">支持 CSV 格式，列：source_type,name,url,category,language,priority</div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="showImport = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { sourcesApi } from '@/api'
import dayjs from 'dayjs'

const loading = ref(false)
const submitting = ref(false)
const sources = ref([])
const dialogVisible = ref(false)
const showImport = ref(false)
const editingRow = ref(null)
const formRef = ref(null)

const filters = reactive({ source_type: '', status: '', category: '' })
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })
const form = reactive({
  source_type: 'rss', name: '', url: '', category: 'general_security',
  language: 'zh', priority: 'medium', notes: '',
})
const rules = {
  source_type: [{ required: true, message: '请选择类型' }],
  name: [{ required: true, message: '请输入名称' }],
}

async function loadSources() {
  loading.value = true
  try {
    const res = await sourcesApi.list({
      page: pagination.page,
      page_size: pagination.pageSize,
      ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)),
    })
    sources.value = res.items
    pagination.total = res.total
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  Object.assign(filters, { source_type: '', status: '', category: '' })
  pagination.page = 1
  loadSources()
}

function openCreate() {
  editingRow.value = null
  Object.assign(form, { source_type: 'rss', name: '', url: '', category: 'general_security', language: 'zh', priority: 'medium', notes: '' })
  dialogVisible.value = true
}

function openEdit(row) {
  editingRow.value = row
  Object.assign(form, { ...row })
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value.validate()
  submitting.value = true
  try {
    if (editingRow.value) {
      await sourcesApi.update(editingRow.value.id, form)
      ElMessage.success('更新成功')
    } else {
      await sourcesApi.create(form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadSources()
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除情报源「${row.name}」？`, '确认删除', { type: 'warning' })
  await sourcesApi.delete(row.id)
  ElMessage.success('删除成功')
  loadSources()
}

async function handleExport() {
  const blob = await sourcesApi.export()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `intel_sources_${dayjs().format('YYYYMMDD')}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

async function handleImportFile(file) {
  try {
    const res = await sourcesApi.import(file.raw)
    ElMessage.success(res.message)
    showImport.value = false
    loadSources()
  } catch {}
}

const typeLabel = (t) => ({ rss: 'RSS', website: '网页', wechat: '微信', search_keyword: '搜索' }[t] || t)
const categoryLabel = (c) => ({ general_security: '通用安全', enterprise_it: '企业IT', automotive: '车联网', compliance: '合规', supply_chain: '供应链' }[c] || c)
const priorityType = (p) => ({ high: 'danger', medium: 'warning', low: 'info' }[p] || 'info')
const statusType = (s) => ({ active: 'success', paused: 'info', error: 'danger' }[s] || 'info')
const statusLabel = (s) => ({ active: '活跃', paused: '暂停', error: '异常' }[s] || s)
const formatDate = (d) => d ? dayjs(d).format('MM-DD HH:mm') : '-'

onMounted(loadSources)
</script>

<style scoped>
.sources-page { max-width: 1400px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { font-size: 18px; font-weight: 600; color: #303133; }
.filter-card { margin-bottom: 0; }
.mt-3 { margin-top: 12px; }
.actions { display: flex; gap: 8px; }
</style>
