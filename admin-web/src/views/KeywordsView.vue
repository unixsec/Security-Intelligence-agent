<!--
  安全情报分析智能体 — 关键词管理页面（简化版）
  版本：v1.0
  作者：alex (unix_sec@163.com)
-->
<template>
  <div class="keywords-page">
    <div class="page-header">
      <h2>关键词管理</h2>
      <div class="actions">
        <el-button @click="showImport = true" plain><el-icon><Upload /></el-icon>批量导入</el-button>
        <el-button @click="handleExport" plain><el-icon><Download /></el-icon>导出</el-button>
        <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新增关键词</el-button>
      </div>
    </div>

    <el-card shadow="never">
      <el-table :data="keywords" v-loading="loading" stripe>
        <el-table-column prop="keyword" label="关键词" min-width="180" />
        <el-table-column prop="category" label="分类" width="120">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ categoryLabel(row.category) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="language" label="语言" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small">{{ row.language.toUpperCase() }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="daily_quota" label="日配额" width="90" align="center" />
        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-switch
              :model-value="row.status === 'active'"
              @change="toggleStatus(row)"
              active-text="启用"
              inactive-text="暂停"
            />
          </template>
        </el-table-column>
        <el-table-column prop="last_used_at" label="最后使用" width="130">
          <template #default="{ row }">{{ formatDate(row.last_used_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
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
        @change="loadKeywords"
      />
    </el-card>

    <!-- 编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="editingRow ? '编辑关键词' : '新增关键词'" width="480px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="关键词">
          <el-input v-model="form.keyword" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="form.category" style="width: 100%">
            <el-option v-for="c in categories" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="语言">
          <el-radio-group v-model="form.language">
            <el-radio value="zh">中文</el-radio>
            <el-radio value="en">English</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="日配额">
          <el-input-number v-model="form.daily_quota" :min="1" :max="50" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- 导入对话框 -->
    <el-dialog v-model="showImport" title="批量导入关键词" width="400px">
      <el-upload drag :auto-upload="false" accept=".csv" :on-change="handleImportFile" :limit="1">
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">拖拽 CSV 文件到此处，或 <em>点击上传</em></div>
      </el-upload>
      <template #footer><el-button @click="showImport = false">关闭</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { keywordsApi } from '@/api'
import dayjs from 'dayjs'

const loading = ref(false), submitting = ref(false), dialogVisible = ref(false), showImport = ref(false)
const keywords = ref([]), editingRow = ref(null)
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })
const form = reactive({ keyword: '', category: 'general_security', language: 'zh', daily_quota: 10 })

const categories = [
  { value: 'general_security', label: '通用安全' },
  { value: 'enterprise_it', label: '企业IT' },
  { value: 'automotive', label: '车联网' },
  { value: 'compliance', label: '合规' },
  { value: 'supply_chain', label: '供应链' },
]
const categoryLabel = (c) => categories.find(x => x.value === c)?.label || c
const formatDate = (d) => d ? dayjs(d).format('MM-DD HH:mm') : '-'

async function loadKeywords() {
  loading.value = true
  try {
    const res = await keywordsApi.list({ page: pagination.page, page_size: pagination.pageSize })
    keywords.value = res.items
    pagination.total = res.total
  } finally { loading.value = false }
}

function openCreate() { editingRow.value = null; Object.assign(form, { keyword: '', category: 'general_security', language: 'zh', daily_quota: 10 }); dialogVisible.value = true }
function openEdit(row) { editingRow.value = row; Object.assign(form, { ...row }); dialogVisible.value = true }

async function handleSubmit() {
  submitting.value = true
  try {
    if (editingRow.value) { await keywordsApi.update(editingRow.value.id, form); ElMessage.success('更新成功') }
    else { await keywordsApi.create(form); ElMessage.success('创建成功') }
    dialogVisible.value = false; loadKeywords()
  } finally { submitting.value = false }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(`确定删除关键词「${row.keyword}」？`, '确认删除', { type: 'warning' })
  await keywordsApi.delete(row.id); ElMessage.success('删除成功'); loadKeywords()
}

async function toggleStatus(row) {
  const newStatus = row.status === 'active' ? 'paused' : 'active'
  await keywordsApi.update(row.id, { status: newStatus })
  row.status = newStatus
}

async function handleExport() {
  const blob = await keywordsApi.export()
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob)
  a.download = `keywords_${dayjs().format('YYYYMMDD')}.csv`; a.click()
}

async function handleImportFile(file) {
  try { const res = await keywordsApi.import(file.raw); ElMessage.success(res.message); showImport.value = false; loadKeywords() } catch {}
}

onMounted(loadKeywords)
</script>

<style scoped>
.keywords-page { max-width: 1200px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { font-size: 18px; font-weight: 600; color: #303133; }
.actions { display: flex; gap: 8px; }
.mt-3 { margin-top: 12px; }
</style>
