<template>
  <el-container style="height: 100vh">
    <!-- Sidebar -->
    <el-aside :width="isCollapsed ? '64px' : '220px'" style="transition: width 0.3s">
      <div class="logo">
        <el-icon :size="24"><Shield /></el-icon>
        <span v-show="!isCollapsed" class="logo-text">SIA</span>
      </div>
      <el-menu
        :default-active="$route.path"
        :collapse="isCollapsed"
        router
        background-color="#001529"
        text-color="#ffffffa6"
        active-text-color="#fff"
      >
        <template v-for="route in menuRoutes" :key="route.path">
          <el-menu-item :index="'/' + route.path">
            <el-icon><component :is="route.meta.icon" /></el-icon>
            <template #title>{{ menuLabel(route) }}</template>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>

    <!-- Main Content -->
    <el-container>
      <el-header class="header">
        <div class="header-left">
          <el-icon
            class="collapse-btn"
            @click="isCollapsed = !isCollapsed"
          >
            <Fold v-if="!isCollapsed" />
            <Expand v-else />
          </el-icon>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item>SIA</el-breadcrumb-item>
            <el-breadcrumb-item>{{ menuLabel($route) }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-tag :type="healthStatus === 'healthy' ? 'success' : 'danger'" size="small">
            {{ healthStatus }}
          </el-tag>
          <!-- v0.4-4: language switcher -->
          <el-dropdown trigger="click" @command="onLocale">
            <span class="user-trigger" :title="t('i18n.switchLanguage')">
              🌐 {{ currentLocaleLabel }}
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-for="loc in supportedLocales" :key="loc.code" :command="loc.code">
                  {{ loc.label }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-dropdown trigger="click" @command="onUserMenu">
            <span class="user-trigger">
              <el-icon><User /></el-icon>
              <span style="margin-left: 6px">{{ auth.user?.username || 'guest' }}</span>
              <el-tag size="small" effect="plain" style="margin-left: 8px">
                {{ auth.user?.role || 'viewer' }}
              </el-tag>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">{{ t('auth.signOut') }}</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessageBox, ElMessage } from 'element-plus'
import { User } from '@element-plus/icons-vue'
import { getHealth } from '../api'
import { useAuthStore } from '../stores/auth'
import { SUPPORTED_LOCALES, setLocale } from '../i18n'

const router = useRouter()
const auth = useAuthStore()
const { t, locale } = useI18n()
const isCollapsed = ref(false)
const healthStatus = ref('unknown')
const supportedLocales = SUPPORTED_LOCALES

const menuRoutes = computed(() => {
  const main = router.options.routes.find(r => r.path === '/')
  const items = (main?.children || []).filter(c => !c.meta?.hidden)
  // Hide admin-only menu items for non-admin roles.
  const role = auth.role
  return items.filter(c => {
    const need = c.meta?.requireRole
    if (!need) return true
    if (need === 'admin') return role === 'admin'
    if (need === 'analyst') return role === 'admin' || role === 'analyst'
    return true
  })
})

function menuLabel(route) {
  const title = route.meta?.title || ''
  // i18n key (e.g. "nav.users") vs hard-coded Chinese label
  if (title.includes('.')) {
    const tr = t(title)
    if (tr && tr !== title) return tr
  }
  return title
}

const currentLocaleLabel = computed(() => {
  return SUPPORTED_LOCALES.find(l => l.code === locale.value)?.label || locale.value
})

onMounted(async () => {
  try {
    const data = await getHealth()
    healthStatus.value = data.status || 'healthy'
  } catch {
    healthStatus.value = 'error'
  }
})

async function onUserMenu (cmd) {
  if (cmd === 'logout') {
    try {
      await ElMessageBox.confirm(t('auth.confirmSignOut'), t('common.confirm'), { type: 'warning' })
    } catch {
      return
    }
    await auth.logout()
    ElMessage.success(t('auth.loggedOut'))
    router.replace('/login')
  }
}

function onLocale (code) {
  setLocale(code)
}
</script>

<style scoped>
.el-aside {
  background-color: #001529;
  overflow: hidden;
}
.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #fff;
  font-size: 20px;
  font-weight: bold;
  border-bottom: 1px solid #ffffff1a;
}
.logo-text {
  letter-spacing: 2px;
}
.header {
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  padding: 0 20px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}
.collapse-btn {
  cursor: pointer;
  font-size: 20px;
}
.el-main {
  padding: 20px;
  background-color: #f0f2f5;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.user-trigger {
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  color: #303133;
  font-size: 13px;
  user-select: none;
}
</style>
