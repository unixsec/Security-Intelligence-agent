<!--
  安全情报分析智能体 — 系统配置页面
  版本：v1.0
  作者：alex (unix_sec@163.com)
-->
<template>
  <div class="config-page">
    <div class="page-header"><h2>系统配置</h2></div>

    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <span>评分模型配置</span>
            <el-button style="float:right" size="small" type="primary" @click="saveConfig('scoring_model')" :loading="saving.scoring_model">保存</el-button>
          </template>
          <el-form label-width="120px" v-if="configs.scoring_model">
            <el-form-item label="模型版本">
              <el-input v-model="configs.scoring_model.version" />
            </el-form-item>
            <el-form-item label="日报最大条数">
              <el-input-number v-model="configs.scoring_model.daily_max" :min="5" :max="20" />
            </el-form-item>
            <el-form-item label="周/月报最大条数">
              <el-input-number v-model="configs.scoring_model.periodic_max" :min="10" :max="50" />
            </el-form-item>
            <el-form-item label="入选阈值分">
              <el-input-number v-model="configs.scoring_model.threshold" :min="0" :max="100" />
            </el-form-item>
            <el-divider content-position="left">各维度权重</el-divider>
            <template v-for="dim in configs.scoring_model.dimensions" :key="dim.name">
              <el-form-item :label="dim.label">
                <el-slider v-model="dim.weight" :min="0" :max="1" :step="0.05" show-input />
              </el-form-item>
            </template>
          </el-form>
          <el-skeleton v-else :rows="6" animated />
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card shadow="never">
          <template #header>
            <span>LLM 模型配置</span>
            <el-button style="float:right" size="small" type="primary" @click="saveConfig('llm_config')" :loading="saving.llm_config">保存</el-button>
          </template>
          <el-form label-width="120px" v-if="configs.llm_config">
            <el-form-item label="Provider">
              <el-select v-model="configs.llm_config.provider">
                <el-option label="DeepSeek" value="deepseek" />
                <el-option label="Qwen" value="qwen" />
                <el-option label="ChatGLM" value="chatglm" />
                <el-option label="Custom" value="custom" />
              </el-select>
            </el-form-item>
            <el-form-item label="API Endpoint">
              <el-input v-model="configs.llm_config.api_endpoint" />
            </el-form-item>
            <el-form-item label="Model Name">
              <el-input v-model="configs.llm_config.model_name" />
            </el-form-item>
            <el-form-item label="超时（秒）">
              <el-input-number v-model="configs.llm_config.timeout" :min="10" :max="300" />
            </el-form-item>
            <el-form-item label="最大并发">
              <el-input-number v-model="configs.llm_config.max_concurrency" :min="1" :max="50" />
            </el-form-item>
            <el-form-item label="最大重试">
              <el-input-number v-model="configs.llm_config.max_retries" :min="1" :max="5" />
            </el-form-item>
          </el-form>
          <el-skeleton v-else :rows="6" animated />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { configApi } from '@/api'

const configs = reactive({ scoring_model: null, llm_config: null })
const saving = reactive({ scoring_model: false, llm_config: false })

async function loadConfig(key) {
  try { const res = await configApi.get(key); configs[key] = res.config_value } catch {}
}

async function saveConfig(key) {
  saving[key] = true
  try {
    await configApi.update(key, { config_value: configs[key] })
    ElMessage.success('配置保存成功，热更新已生效')
  } finally { saving[key] = false }
}

onMounted(() => { loadConfig('scoring_model'); loadConfig('llm_config') })
</script>

<style scoped>
.config-page { max-width: 1200px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.page-header h2 { font-size: 18px; font-weight: 600; color: #303133; }
</style>
