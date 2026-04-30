<template>
  <div>
    <el-card>
      <template #header>
        <div class="card-head">
          <span>{{ t('apiKeys.title') }}</span>
          <div>
            <el-button size="small" @click="load">{{ t('common.refresh') }}</el-button>
            <el-button type="primary" size="small" @click="openCreate">{{ t('apiKeys.addNew') }}</el-button>
          </div>
        </div>
      </template>

      <el-alert :title="t('apiKeys.notice')" type="info" :closable="false" style="margin-bottom: 12px" />

      <el-table :data="rows" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" :label="t('apiKeys.name')" min-width="150" />
        <el-table-column prop="role" :label="t('users.role')" width="100">
          <template #default="{ row }">
            <el-tag :type="roleTagType(row.role)" size="small">{{ row.role }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('apiKeys.scopes')" min-width="240">
          <template #default="{ row }">
            <el-tag v-for="s in row.scopes" :key="s" size="small" effect="plain" style="margin-right: 4px">{{ s }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" :label="t('apiKeys.description')" min-width="180" show-overflow-tooltip />
        <el-table-column :label="t('apiKeys.expires')" width="160">
          <template #default="{ row }">{{ fmt(row.expires_at) || '∞' }}</template>
        </el-table-column>
        <el-table-column :label="t('apiKeys.lastUsed')" width="160">
          <template #default="{ row }">{{ fmt(row.last_used_at) }}</template>
        </el-table-column>
        <el-table-column prop="created_by" :label="t('apiKeys.createdBy')" width="140" />
        <el-table-column :label="t('apiKeys.statusLabel')" width="100">
          <template #default="{ row }">
            <el-tag :type="row.disabled ? 'info' : 'success'" size="small">
              {{ row.disabled ? t('apiKeys.revoked') : 'active' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('common.actions')" width="200" fixed="right">
          <template #default="{ row }">
            <el-popconfirm :title="t('apiKeys.confirmRevoke')" @confirm="onRevoke(row)">
              <template #reference>
                <el-button size="small" type="danger" :disabled="row.disabled">
                  {{ t('apiKeys.revoke') }}
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Create dialog -->
    <el-dialog v-model="dlg.visible" :title="t('apiKeys.createTitle')" width="540px">
      <el-form :model="dlg.form" label-width="110px">
        <el-form-item :label="t('apiKeys.name')">
          <el-input v-model="dlg.form.name" />
        </el-form-item>
        <el-form-item :label="t('users.role')">
          <el-select v-model="dlg.form.role" style="width: 100%">
            <el-option v-for="r in ['admin','analyst','viewer']" :key="r" :label="r" :value="r" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('apiKeys.scopes')">
          <el-select v-model="dlg.form.scopes" multiple filterable allow-create
                     :placeholder="t('apiKeys.scopesHint')" style="width: 100%">
            <el-option label="* (all)" value="*" />
            <el-option label="/api/v1/intelligence" value="/api/v1/intelligence" />
            <el-option label="/api/v1/reports" value="/api/v1/reports" />
            <el-option label="/api/v1/sources" value="/api/v1/sources" />
            <el-option label="/api/v1/dashboard" value="/api/v1/dashboard" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('apiKeys.description')">
          <el-input v-model="dlg.form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item :label="t('apiKeys.ttl')">
          <el-input-number v-model="dlg.form.expires_in_days" :min="0" :max="3650" />
          <span style="margin-left: 8px; color: #909399; font-size: 12px">
            {{ dlg.form.expires_in_days ? t('apiKeys.ttlDays', { n: dlg.form.expires_in_days }) : t('apiKeys.noExpiry') }}
          </span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg.visible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="dlg.saving" @click="onCreate">{{ t('common.create') }}</el-button>
      </template>
    </el-dialog>

    <!-- One-time plaintext dialog -->
    <el-dialog v-model="onceDlg.visible" :title="t('apiKeys.plaintextTitle')" width="560px" :close-on-click-modal="false">
      <el-alert :title="t('apiKeys.plaintextHint')" type="warning" :closable="false" />
      <el-input v-model="onceDlg.plaintext" readonly type="textarea" :rows="2" style="margin-top: 12px; font-family: monospace" />
      <template #footer>
        <el-button type="primary" @click="copyPlaintext">{{ t('apiKeys.copyKey') }}</el-button>
        <el-button @click="onceDlg.visible = false">{{ t('common.confirm') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import { listApiKeys, createApiKey, revokeApiKey } from '../api'

const { t } = useI18n()
const rows = ref([])
const loading = ref(false)

const dlg = reactive({
  visible: false, saving: false,
  form: { name: '', role: 'viewer', scopes: ['*'], description: '', expires_in_days: 365 },
})
const onceDlg = reactive({ visible: false, plaintext: '' })

function fmt(s) { return s ? dayjs(s).format('YYYY-MM-DD HH:mm') : '' }
function roleTagType(r) { return r === 'admin' ? 'danger' : r === 'analyst' ? 'warning' : 'info' }

async function load() {
  loading.value = true
  try {
    rows.value = await listApiKeys({ include_disabled: true })
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || 'load failed')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  dlg.form = { name: '', role: 'viewer', scopes: ['*'], description: '', expires_in_days: 365 }
  dlg.visible = true
}

async function onCreate() {
  if (!dlg.form.name || dlg.form.name.length < 2) return ElMessage.warning(t('apiKeys.nameRequired'))
  dlg.saving = true
  try {
    const payload = { ...dlg.form }
    if (!payload.expires_in_days || payload.expires_in_days <= 0) {
      delete payload.expires_in_days
    }
    const resp = await createApiKey(payload)
    onceDlg.plaintext = resp.plaintext
    onceDlg.visible = true
    dlg.visible = false
    await load()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || 'create failed')
  } finally {
    dlg.saving = false
  }
}

async function onRevoke(row) {
  try {
    await revokeApiKey(row.id)
    ElMessage.success(t('apiKeys.revokeOk'))
    await load()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || 'failed')
  }
}

async function copyPlaintext() {
  try {
    await navigator.clipboard.writeText(onceDlg.plaintext)
    ElMessage.success(t('apiKeys.copied'))
  } catch {
    ElMessage.warning(t('apiKeys.copyManual'))
  }
}

onMounted(load)
</script>

<style scoped>
.card-head { display: flex; justify-content: space-between; align-items: center; }
</style>
