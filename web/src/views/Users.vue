<template>
  <div>
    <el-card>
      <template #header>
        <div class="card-head">
          <span>{{ t('users.title') }}</span>
          <div>
            <el-input v-model="filter.keyword" :placeholder="t('common.search')" size="small" clearable
                      style="width: 220px; margin-right: 8px" @keyup.enter="load" @clear="load" />
            <el-select v-model="filter.role" size="small" clearable :placeholder="t('users.role')" style="width: 130px; margin-right: 8px">
              <el-option v-for="r in ['admin','analyst','viewer']" :key="r" :label="r" :value="r" />
            </el-select>
            <el-select v-model="filter.status" size="small" clearable :placeholder="t('users.statusLabel')" style="width: 120px; margin-right: 8px">
              <el-option label="active" value="active" />
              <el-option label="disabled" value="disabled" />
            </el-select>
            <el-button size="small" @click="load">{{ t('common.refresh') }}</el-button>
            <el-button type="primary" size="small" @click="openCreate">{{ t('users.addNew') }}</el-button>
          </div>
        </div>
      </template>

      <el-table :data="rows" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="username" :label="t('users.username')" min-width="120" />
        <el-table-column prop="display_name" :label="t('users.displayName')" min-width="120" />
        <el-table-column prop="email" label="Email" min-width="180" show-overflow-tooltip />
        <el-table-column prop="role" :label="t('users.role')" width="100">
          <template #default="{ row }">
            <el-tag :type="roleTagType(row.role)" size="small">{{ row.role }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" :label="t('users.statusLabel')" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="auth_provider" label="Provider" width="100" />
        <el-table-column prop="last_login_at" :label="t('users.lastLogin')" width="170">
          <template #default="{ row }">{{ fmt(row.last_login_at) }}</template>
        </el-table-column>
        <el-table-column :label="t('common.actions')" width="240" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">{{ t('common.edit') }}</el-button>
            <el-button size="small" @click="openResetPwd(row)" :disabled="row.auth_provider !== 'local'">
              {{ t('users.resetPwd') }}
            </el-button>
            <el-popconfirm :title="t('users.confirmDisable')" @confirm="onDelete(row)">
              <template #reference>
                <el-button size="small" type="danger" :disabled="row.status !== 'active'">
                  {{ t('users.disable') }}
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Create / edit dialog -->
    <el-dialog v-model="dlg.visible" :title="dlg.editing ? t('users.editTitle') : t('users.createTitle')" width="540px">
      <el-form :model="dlg.form" ref="formRef" :rules="rules" label-width="120px">
        <el-form-item :label="t('users.username')" prop="username" v-if="!dlg.editing">
          <el-input v-model="dlg.form.username" />
        </el-form-item>
        <el-form-item label="Email" prop="email">
          <el-input v-model="dlg.form.email" />
        </el-form-item>
        <el-form-item :label="t('users.displayName')" prop="display_name">
          <el-input v-model="dlg.form.display_name" />
        </el-form-item>
        <el-form-item :label="t('users.role')" prop="role">
          <el-select v-model="dlg.form.role" style="width: 100%">
            <el-option v-for="r in ['admin','analyst','viewer']" :key="r" :label="r" :value="r" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="dlg.editing" :label="t('users.statusLabel')" prop="status">
          <el-select v-model="dlg.form.status" style="width: 100%">
            <el-option label="active" value="active" />
            <el-option label="disabled" value="disabled" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="!dlg.editing" :label="t('users.password')" prop="password">
          <el-input v-model="dlg.form.password" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg.visible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="dlg.saving" @click="onSave">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- Reset password dialog -->
    <el-dialog v-model="rpw.visible" :title="t('users.resetPwd')" width="420px">
      <el-form :model="rpw.form" label-width="120px">
        <el-form-item :label="t('users.newPassword')">
          <el-input v-model="rpw.form.new_password" type="password" show-password />
        </el-form-item>
        <el-alert :title="t('users.resetPwdHint')" type="warning" :closable="false" />
      </el-form>
      <template #footer>
        <el-button @click="rpw.visible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="rpw.saving" @click="onReset">{{ t('common.confirm') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import { listUsers, createUser, updateUser, deleteUser, resetUserPassword } from '../api'

const { t } = useI18n()
const rows = ref([])
const loading = ref(false)
const filter = reactive({ keyword: '', role: '', status: '' })
const formRef = ref(null)

const dlg = reactive({
  visible: false, editing: false, saving: false,
  form: { id: null, username: '', email: '', display_name: '', role: 'viewer', password: '', status: 'active' },
})
const rpw = reactive({ visible: false, saving: false, form: { id: null, new_password: '' } })

const rules = {
  username: [{ required: true, min: 2, max: 100, message: 'required' }],
  email: [{ required: true, type: 'email', message: 'invalid email' }],
  role: [{ required: true }],
  password: [{ required: true, min: 8, message: 'min 8 chars' }],
}

function fmt(s) { return s ? dayjs(s).format('YYYY-MM-DD HH:mm') : '-' }
function roleTagType(r) { return r === 'admin' ? 'danger' : r === 'analyst' ? 'warning' : 'info' }

async function load() {
  loading.value = true
  try {
    const params = {}
    if (filter.keyword) params.keyword = filter.keyword
    if (filter.role) params.role = filter.role
    if (filter.status) params.status = filter.status
    rows.value = await listUsers(params)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || 'load failed')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  dlg.editing = false
  dlg.form = { id: null, username: '', email: '', display_name: '', role: 'viewer', password: '', status: 'active' }
  dlg.visible = true
}
function openEdit(row) {
  dlg.editing = true
  dlg.form = { id: row.id, username: row.username, email: row.email, display_name: row.display_name, role: row.role, status: row.status, password: '' }
  dlg.visible = true
}
function openResetPwd(row) {
  rpw.form = { id: row.id, new_password: '' }
  rpw.visible = true
}

async function onSave() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  dlg.saving = true
  try {
    if (dlg.editing) {
      await updateUser(dlg.form.id, {
        email: dlg.form.email,
        display_name: dlg.form.display_name,
        role: dlg.form.role,
        status: dlg.form.status,
      })
      ElMessage.success(t('users.updateOk'))
    } else {
      await createUser({
        username: dlg.form.username,
        email: dlg.form.email,
        display_name: dlg.form.display_name || dlg.form.username,
        role: dlg.form.role,
        password: dlg.form.password,
      })
      ElMessage.success(t('users.createOk'))
    }
    dlg.visible = false
    await load()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || 'save failed')
  } finally {
    dlg.saving = false
  }
}

async function onReset() {
  if (!rpw.form.new_password || rpw.form.new_password.length < 8) {
    return ElMessage.warning('min 8 chars')
  }
  rpw.saving = true
  try {
    await resetUserPassword(rpw.form.id, { new_password: rpw.form.new_password })
    ElMessage.success(t('users.resetOk'))
    rpw.visible = false
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || 'reset failed')
  } finally {
    rpw.saving = false
  }
}

async function onDelete(row) {
  try {
    await deleteUser(row.id)
    ElMessage.success(t('users.disableOk'))
    await load()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || 'failed')
  }
}

onMounted(load)
</script>

<style scoped>
.card-head { display: flex; justify-content: space-between; align-items: center; }
</style>
