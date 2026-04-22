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
            <template #title>{{ route.meta.title }}</template>
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
            <el-breadcrumb-item>{{ $route.meta.title }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-tag :type="healthStatus === 'healthy' ? 'success' : 'danger'" size="small">
            {{ healthStatus }}
          </el-tag>
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
import { getHealth } from '../api'

const router = useRouter()
const isCollapsed = ref(false)
const healthStatus = ref('unknown')

const menuRoutes = computed(() => {
  const main = router.options.routes.find(r => r.path === '/')
  return (main?.children || []).filter(c => !c.meta?.hidden)
})

onMounted(async () => {
  try {
    const data = await getHealth()
    healthStatus.value = data.status || 'healthy'
  } catch {
    healthStatus.value = 'error'
  }
})
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
</style>
