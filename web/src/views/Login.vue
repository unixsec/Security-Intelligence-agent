<template>
  <div class="login-wrap">
    <el-card class="login-card" shadow="always">
      <template #header>
        <div class="header">
          <div class="title">SIA</div>
          <div class="subtitle">Security Intelligence Agent</div>
        </div>
      </template>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @keyup.enter="onSubmit"
      >
        <el-form-item label="Username" prop="username">
          <el-input
            v-model="form.username"
            autocomplete="username"
            :prefix-icon="User"
          />
        </el-form-item>

        <el-form-item label="Password" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            autocomplete="current-password"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>

        <el-form-item label="Provider" prop="provider">
          <el-select v-model="form.provider" style="width: 100%">
            <el-option label="Local" value="local" />
            <el-option label="LDAP / AD" value="ldap" />
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            :loading="loading"
            style="width: 100%"
            @click="onSubmit"
          >
            Sign in
          </el-button>
        </el-form-item>

        <div v-if="oidcProviders.length" class="oidc-row">
          <el-divider content-position="center">or</el-divider>
          <el-button
            v-for="p in oidcProviders"
            :key="p.key"
            plain
            style="width: 100%; margin-bottom: 8px"
            @click="onOidc(p)"
          >
            Continue with {{ p.display_name }}
          </el-button>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Lock, User } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'
import { listOidcProviders } from '../api'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const formRef = ref(null)
const loading = ref(false)
const oidcProviders = ref([])

const form = reactive({
  username: '',
  password: '',
  provider: 'local',
})

const rules = {
  username: [{ required: true, message: 'Username required', trigger: 'blur' }],
  password: [{ required: true, message: 'Password required', trigger: 'blur' }],
  provider: [{ required: true, trigger: 'change' }],
}

onMounted(async () => {
  // Best-effort fetch — fine if disabled.
  try {
    oidcProviders.value = await listOidcProviders()
  } catch (_) { /* ignore */ }
})

async function onSubmit () {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  loading.value = true
  try {
    await auth.login({ ...form })
    ElMessage.success('Signed in')
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.replace(redirect)
  } catch (e) {
    const detail = e.response?.data?.detail || 'Login failed'
    ElMessage.error(detail)
  } finally {
    loading.value = false
  }
}

function onOidc (p) {
  // Trigger /auth/oidc/authorize on the server which returns the IdP URL.
  // Implementation is provider-specific and outside FE-1 scope; show a hint.
  ElMessage.info(`OIDC flow for ${p.display_name} not wired in this build.`)
}
</script>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
  padding: 16px;
}
.login-card {
  width: 360px;
}
.header { text-align: center; }
.title { font-size: 28px; font-weight: 700; color: #303133; }
.subtitle { color: #909399; font-size: 13px; margin-top: 4px; }
.oidc-row { margin-top: 8px; }
</style>
