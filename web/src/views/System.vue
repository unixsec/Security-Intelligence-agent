<template>
  <div>
    <el-row :gutter="16">
      <!-- Health -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-head">
              <span>{{ t('system.health') }}</span>
              <el-button size="small" @click="loadHealth">{{ t('common.refresh') }}</el-button>
            </div>
          </template>
          <el-descriptions :column="1" border v-if="health">
            <el-descriptions-item :label="t('system.status')">
              <el-tag :type="health.status === 'healthy' ? 'success' : 'danger'">{{ health.status }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item :label="t('system.version')">{{ health.version }}</el-descriptions-item>
            <el-descriptions-item :label="t('system.uptime')">{{ formatUptime(health.uptime_seconds) }}</el-descriptions-item>
            <el-descriptions-item label="MySQL">
              <el-tag :type="health.database === 'healthy' ? 'success' : 'danger'" size="small">{{ health.database }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="Redis">
              <el-tag :type="health.redis === 'healthy' ? 'success' : 'danger'" size="small">{{ health.redis }}</el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <!-- Quick actions -->
      <el-col :span="12">
        <el-card>
          <template #header>{{ t('system.quickActions') }}</template>
          <div class="action-grid">
            <el-button @click="handleReloadPrompts" :loading="reloading">
              <el-icon><Refresh /></el-icon> {{ t('system.reloadPrompts') }}
            </el-button>
            <el-button @click="loadAll">
              <el-icon><DataLine /></el-icon> {{ t('system.refreshAll') }}
            </el-button>
            <el-button @click="goMetrics" type="info">
              <el-icon><Monitor /></el-icon> /metrics
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Circuit breakers -->
    <el-card style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>{{ t('system.circuitBreakers') }}</span>
          <el-button size="small" @click="loadCircuits">{{ t('common.refresh') }}</el-button>
        </div>
      </template>
      <el-table :data="circuits" v-if="circuits.length" size="small">
        <el-table-column prop="kind" :label="t('system.cbKind')" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="row.kind === 'llm' ? 'warning' : 'info'">{{ row.kind }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="name" :label="t('system.cbName')" width="200" />
        <el-table-column prop="state" :label="t('system.cbState')" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="cbStateType(row.state)">{{ row.state }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="failure_count" :label="t('system.cbFailures')" width="120" />
        <el-table-column prop="success_count" :label="t('system.cbSuccess')" width="120" />
        <el-table-column prop="last_failure_time" :label="t('system.cbLastFail')" />
      </el-table>
      <el-empty v-else description="-" :image-size="60" />
    </el-card>

    <!-- Streams -->
    <el-card style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>{{ t('system.streams') }}</span>
          <el-button size="small" @click="loadStreams">{{ t('common.refresh') }}</el-button>
        </div>
      </template>
      <el-table :data="streams" v-if="streams.length" size="small">
        <el-table-column prop="stream" :label="t('system.streamName')" width="240" />
        <el-table-column prop="length" :label="t('system.streamLength')" width="120">
          <template #default="{ row }">
            <el-tag :type="row.length > 1000 ? 'danger' : row.length > 200 ? 'warning' : 'success'" size="small">
              {{ row.length }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('system.consumerGroups')">
          <template #default="{ row }">
            <span v-for="g in row.groups" :key="g.name" style="margin-right: 12px; font-size: 12px">
              <strong>{{ g.name }}</strong>:
              {{ t('system.consumers') }}={{ g.consumers }}, {{ t('system.pending') }}={{ g.pending }}
            </span>
            <span v-if="!row.groups || !row.groups.length" style="color: #909399">-</span>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="-" :image-size="60" />
    </el-card>

    <!-- DLQ -->
    <el-card style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>{{ t('system.dlq') }} ({{ dlq.count }})</span>
          <el-button size="small" @click="loadDlq">{{ t('common.refresh') }}</el-button>
        </div>
      </template>
      <el-table :data="dlq.items" v-if="dlq.items.length" size="small">
        <el-table-column prop="id" label="msg-id" width="200" />
        <el-table-column :label="t('system.dlqError')">
          <template #default="{ row }">{{ row.data?.error || '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('system.dlqOriginalStream')">
          <template #default="{ row }">{{ row.data?.original_stream || '-' }}</template>
        </el-table-column>
        <el-table-column label="intel_id">
          <template #default="{ row }">{{ row.data?.intel_id || '-' }}</template>
        </el-table-column>
      </el-table>
      <el-empty v-else :description="t('system.dlqEmpty')" :image-size="60" />
    </el-card>

    <!-- Scheduler -->
    <el-card style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>{{ t('system.scheduler') }}</span>
          <el-button size="small" @click="loadScheduler">{{ t('common.refresh') }}</el-button>
        </div>
      </template>
      <el-table :data="jobs" v-if="jobs.length" size="small">
        <el-table-column prop="id" :label="t('system.jobId')" width="220" />
        <el-table-column prop="name" :label="t('system.jobName')" width="220" />
        <el-table-column prop="trigger" :label="t('system.jobTrigger')" />
        <el-table-column prop="next_run" :label="t('system.jobNextRun')" width="200" />
      </el-table>
      <el-empty v-else description="-" :image-size="60" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Refresh, DataLine, Monitor } from '@element-plus/icons-vue'
import {
  getHealth, reloadPrompts, listCircuitBreakers, listStreams,
  peekDlq, listSchedulerJobs,
} from '../api'

const { t } = useI18n()
const health = ref(null)
const circuits = ref([])
const streams = ref([])
const dlq = ref({ items: [], count: 0 })
const jobs = ref([])
const reloading = ref(false)

function cbStateType(s) {
  if (s === 'closed') return 'success'
  if (s === 'half_open') return 'warning'
  if (s === 'open') return 'danger'
  return 'info'
}

function formatUptime(s) {
  if (!s) return '-'
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  return `${h}h ${m}m`
}

async function loadHealth() {
  try { health.value = await getHealth() } catch { health.value = { status: 'error' } }
}
async function loadCircuits() {
  try { circuits.value = await listCircuitBreakers() } catch { circuits.value = [] }
}
async function loadStreams() {
  try { streams.value = await listStreams() } catch { streams.value = [] }
}
async function loadDlq() {
  try { dlq.value = await peekDlq(50) } catch { dlq.value = { items: [], count: 0 } }
}
async function loadScheduler() {
  try { jobs.value = await listSchedulerJobs() } catch { jobs.value = [] }
}
async function loadAll() {
  await Promise.all([loadHealth(), loadCircuits(), loadStreams(), loadDlq(), loadScheduler()])
}

async function handleReloadPrompts() {
  reloading.value = true
  try {
    await reloadPrompts()
    ElMessage.success(t('system.reloadOk'))
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || 'failed')
  } finally {
    reloading.value = false
  }
}

function goMetrics() {
  window.open('/metrics', '_blank')
}

onMounted(loadAll)
</script>

<style scoped>
.card-head { display: flex; justify-content: space-between; align-items: center; }
.action-grid { display: flex; gap: 12px; flex-wrap: wrap; }
</style>
