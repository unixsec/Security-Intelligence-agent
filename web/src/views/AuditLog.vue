<template>
  <div>
    <el-card>
      <template #header>
        <div class="card-head">
          <span>{{ t('audit.title') }}</span>
          <div>
            <el-button size="small" @click="loadStats">{{ t('audit.refreshStats') }}</el-button>
            <el-button type="primary" size="small" @click="load">{{ t('common.search') }}</el-button>
          </div>
        </div>
      </template>

      <!-- Filter bar -->
      <el-form :model="filter" inline size="small" style="margin-bottom: 12px">
        <el-form-item :label="t('audit.actor')">
          <el-input v-model="filter.actor" clearable style="width: 160px" />
        </el-form-item>
        <el-form-item :label="t('audit.eventType')">
          <el-input v-model="filter.event_type" clearable style="width: 160px"
                    :placeholder="t('audit.eventTypeHint')" />
        </el-form-item>
        <el-form-item :label="t('audit.action')">
          <el-input v-model="filter.action" clearable style="width: 120px" />
        </el-form-item>
        <el-form-item :label="t('audit.timeRange')">
          <el-date-picker v-model="filter.range" type="datetimerange" value-format="YYYY-MM-DDTHH:mm:ss"
                          :range-separator="t('audit.to')" :start-placeholder="t('audit.from')"
                          :end-placeholder="t('audit.until')" />
        </el-form-item>
        <el-form-item :label="t('audit.limit')">
          <el-input-number v-model="filter.limit" :min="1" :max="1000" />
        </el-form-item>
      </el-form>

      <!-- Stats summary -->
      <el-row :gutter="12" style="margin-bottom: 12px">
        <el-col v-for="s in stats" :key="s.event_type" :span="4">
          <el-card shadow="hover">
            <div style="font-size: 12px; color: #909399">{{ s.event_type }}</div>
            <div style="font-size: 22px; font-weight: 600">{{ s.count }}</div>
          </el-card>
        </el-col>
      </el-row>

      <el-table :data="rows" v-loading="loading" stripe size="small">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column :label="t('audit.occurredAt')" width="170">
          <template #default="{ row }">{{ fmt(row.occurred_at) }}</template>
        </el-table-column>
        <el-table-column prop="actor" :label="t('audit.actor')" width="160" />
        <el-table-column prop="actor_ip" label="IP" width="130" />
        <el-table-column prop="event_type" :label="t('audit.eventType')" width="180" />
        <el-table-column prop="entity_type" label="Entity" width="120" />
        <el-table-column prop="entity_id" label="ID" width="100" />
        <el-table-column prop="action" :label="t('audit.action')" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="actionTagType(row.action)">{{ row.action }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('audit.details')">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="showDetails(row)">{{ t('audit.viewDetail') }}</el-button>
          </template>
        </el-table-column>
        <el-table-column :label="t('audit.hash')" width="100">
          <template #default="{ row }">
            <el-tooltip :content="row.current_hash"><code>{{ (row.current_hash || '').slice(0, 8) }}…</code></el-tooltip>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dlg.visible" :title="t('audit.entryDetail')" width="640px">
      <pre v-if="dlg.row" style="background: #f5f7fa; padding: 12px; border-radius: 4px; overflow: auto">{{ JSON.stringify(dlg.row, null, 2) }}</pre>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import { listAuditLogs, getAuditStats } from '../api'

const { t } = useI18n()
const rows = ref([])
const stats = ref([])
const loading = ref(false)
const filter = reactive({ actor: '', event_type: '', action: '', range: null, limit: 200 })
const dlg = reactive({ visible: false, row: null })

function fmt(s) { return s ? dayjs(s).format('YYYY-MM-DD HH:mm:ss') : '-' }
function actionTagType(a) {
  if (['create', 'update'].includes(a)) return 'warning'
  if (a === 'delete') return 'danger'
  if (a === 'login' || a === 'access') return 'success'
  return 'info'
}

async function load() {
  loading.value = true
  try {
    const params = { limit: filter.limit }
    if (filter.actor) params.actor = filter.actor
    if (filter.event_type) params.event_type = filter.event_type
    if (filter.action) params.action = filter.action
    if (filter.range && filter.range.length === 2) {
      params.since = filter.range[0]
      params.until = filter.range[1]
    }
    rows.value = await listAuditLogs(params)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || 'load failed')
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    stats.value = (await getAuditStats(24)).slice(0, 6)
  } catch {
    stats.value = []
  }
}

function showDetails(row) {
  dlg.row = row
  dlg.visible = true
}

onMounted(() => { load(); loadStats() })
</script>

<style scoped>
.card-head { display: flex; justify-content: space-between; align-items: center; }
</style>
