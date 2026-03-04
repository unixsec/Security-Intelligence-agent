<!--
  安全情报分析智能体 — 管理控制台布局框架
  版本：v1.0
  作者：alex (unix_sec@163.com)
-->
<template>
  <el-container class="layout-container">
    <!-- 侧边栏 -->
    <el-aside :width="isCollapsed ? '64px' : '220px'" class="sidebar">
      <div class="logo" :class="{ collapsed: isCollapsed }">
        <el-icon size="24" color="#409eff"><Shield /></el-icon>
        <span v-if="!isCollapsed" class="logo-text">情报智能体</span>
      </div>
      <el-menu
        :default-active="$route.path"
        router
        :collapse="isCollapsed"
        background-color="#1a1f2e"
        text-color="#a8b2c8"
        active-text-color="#409eff"
        class="side-menu"
      >
        <el-menu-item index="/dashboard">
          <el-icon><DataBoard /></el-icon>
          <template #title>系统概览</template>
        </el-menu-item>
        <el-menu-item index="/sources">
          <el-icon><Connection /></el-icon>
          <template #title>情报源管理</template>
        </el-menu-item>
        <el-menu-item index="/keywords">
          <el-icon><Search /></el-icon>
          <template #title>关键词管理</template>
        </el-menu-item>
        <el-menu-item index="/intel">
          <el-icon><Document /></el-icon>
          <template #title>情报列表</template>
        </el-menu-item>
        <el-menu-item index="/reports">
          <el-icon><Memo /></el-icon>
          <template #title>报告管理</template>
        </el-menu-item>
        <el-divider />
        <el-menu-item index="/config">
          <el-icon><Setting /></el-icon>
          <template #title>系统配置</template>
        </el-menu-item>
        <el-menu-item index="/audit">
          <el-icon><Tickets /></el-icon>
          <template #title>审计日志</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <!-- 顶部导航栏 -->
      <el-header class="top-header">
        <el-icon
          class="collapse-btn"
          size="20"
          @click="isCollapsed = !isCollapsed"
        >
          <Fold v-if="!isCollapsed" />
          <Expand v-else />
        </el-icon>
        <div class="breadcrumb">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item>{{ currentTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-tag :type="healthStatus" size="small" class="health-tag">
            <el-icon><CircleCheck v-if="healthStatus === 'success'" /><Warning v-else /></el-icon>
            {{ healthLabel }}
          </el-tag>
          <el-text size="small" type="info" class="ml-2">
            v1.0 · alex
          </el-text>
        </div>
      </el-header>

      <!-- 主内容区 -->
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { dashboardApi } from '@/api'

const route = useRoute()
const isCollapsed = ref(false)
const healthData = ref(null)

const currentTitle = computed(() => route.meta.title || '')
const healthStatus = computed(() => {
  if (!healthData.value) return 'info'
  return healthData.value.status === 'healthy' ? 'success' : 'warning'
})
const healthLabel = computed(() => {
  if (!healthData.value) return '检测中...'
  const map = { healthy: '系统正常', degraded: '部分降级', critical: '严重异常' }
  return map[healthData.value.status] || '未知'
})

onMounted(async () => {
  try {
    healthData.value = await dashboardApi.health()
  } catch {}
})
</script>

<style scoped>
.layout-container {
  height: 100vh;
}

.sidebar {
  background-color: #1a1f2e;
  transition: width 0.3s;
  overflow: hidden;
}

.logo {
  display: flex;
  align-items: center;
  padding: 16px 20px;
  gap: 10px;
  border-bottom: 1px solid #2d3348;
  min-height: 60px;
}

.logo.collapsed {
  padding: 16px 20px;
  justify-content: center;
}

.logo-text {
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  white-space: nowrap;
}

.side-menu {
  border-right: none;
  height: calc(100vh - 60px);
  overflow-y: auto;
}

.top-header {
  display: flex;
  align-items: center;
  gap: 16px;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  padding: 0 20px;
  height: 56px;
}

.collapse-btn {
  cursor: pointer;
  color: #606266;
  flex-shrink: 0;
}

.breadcrumb {
  flex: 1;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.health-tag {
  display: flex;
  align-items: center;
  gap: 4px;
}

.ml-2 {
  margin-left: 4px;
}

.main-content {
  background: #f5f7fa;
  overflow-y: auto;
  padding: 20px;
}
</style>
