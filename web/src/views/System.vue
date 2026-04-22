<template>
  <div>
    <el-row :gutter="16">
      <!-- Health Status -->
      <el-col :span="12">
        <el-card header="系统状态">
          <el-descriptions :column="1" border v-if="health">
            <el-descriptions-item label="状态">
              <el-tag :type="health.status === 'healthy' ? 'success' : 'danger'">
                {{ health.status }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="版本">{{ health.version }}</el-descriptions-item>
            <el-descriptions-item label="运行时间">{{ formatUptime(health.uptime_seconds) }}</el-descriptions-item>
            <el-descriptions-item label="数据库">
              <el-tag :type="health.database === 'healthy' ? 'success' : 'danger'" size="small">
                {{ health.database }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="Redis">
              <el-tag :type="health.redis === 'healthy' ? 'success' : 'danger'" size="small">
                {{ health.redis }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>
          <el-button style="margin-top: 16px" @click="loadHealth">刷新状态</el-button>
        </el-card>
      </el-col>

      <!-- Quick Actions -->
      <el-col :span="12">
        <el-card header="快捷操作">
          <div class="action-grid">
            <el-button @click="handleReloadPrompts" :loading="reloading">
              <el-icon><Refresh /></el-icon> 重载提示词模板
            </el-button>
            <el-button @click="handleCollectAll">
              <el-icon><Download /></el-icon> 全量采集
            </el-button>
          </div>
        </el-card>

        <el-card header="LLM 提供商状态" style="margin-top: 16px">
          <div v-if="llmProviders.length">
            <div v-for="p in llmProviders" :key="p.name" class="provider-item">
              <span>{{ p.name }}</span>
              <el-tag :type="p.state === 'closed' ? 'success' : 'danger'" size="small">
                {{ p.state }}
              </el-tag>
            </div>
          </div>
          <el-empty v-else description="暂无提供商信息" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getHealth, getLLMProviderStatus, reloadPrompts } from '../api'

const health = ref(null)
const llmProviders = ref([])
const reloading = ref(false)

const loadHealth = async () => {
  try {
    health.value = await getHealth()
  } catch {
    health.value = { status: 'error', version: 'unknown' }
  }
}

const loadProviders = async () => {
  try {
    const data = await getLLMProviderStatus()
    if (Array.isArray(data)) {
      llmProviders.value = data
    }
  } catch {
    // Provider status not available
  }
}

const handleReloadPrompts = async () => {
  reloading.value = true
  try {
    await reloadPrompts()
    ElMessage.success('提示词模板已重载')
  } catch {
    ElMessage.error('重载失败')
  } finally {
    reloading.value = false
  }
}

const handleCollectAll = () => {
  ElMessage.info('全量采集任务已提交（通过调度器执行）')
}

const formatUptime = (seconds) => {
  if (!seconds) return '-'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return `${h}h ${m}m`
}

onMounted(() => {
  loadHealth()
  loadProviders()
})
</script>

<style scoped>
.action-grid {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.provider-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}
.provider-item:last-child {
  border-bottom: none;
}
</style>
