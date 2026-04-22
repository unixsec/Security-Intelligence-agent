<template>
  <div v-loading="loading">
    <el-page-header @back="$router.back()" :title="'返回列表'">
      <template #content>
        <el-tag :type="priorityTagType(detail.priority_level)" class="mr-2">
          {{ detail.priority_level }}
        </el-tag>
        {{ detail.title }}
      </template>
    </el-page-header>

    <el-row :gutter="16" style="margin-top: 20px">
      <!-- Left: Main Content -->
      <el-col :span="16">
        <el-card header="情报内容">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="标题">{{ detail.title }}</el-descriptions-item>
            <el-descriptions-item label="中文标题">{{ detail.title_zh || '-' }}</el-descriptions-item>
            <el-descriptions-item label="分类">{{ detail.primary_category }} / {{ detail.secondary_category }}</el-descriptions-item>
            <el-descriptions-item label="TLP">
              <el-tag :type="tlpType(detail.tlp_level)" size="small">{{ detail.tlp_level }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="来源">{{ detail.source_name }}</el-descriptions-item>
            <el-descriptions-item label="CVE">{{ detail.cve_id || '-' }}</el-descriptions-item>
            <el-descriptions-item label="CVSS">{{ detail.cvss_score || '-' }}</el-descriptions-item>
            <el-descriptions-item label="EPSS">{{ detail.epss_score || '-' }}</el-descriptions-item>
            <el-descriptions-item label="KEV">
              <el-tag v-if="detail.is_kev" type="danger" size="small">是</el-tag>
              <span v-else>否</span>
            </el-descriptions-item>
            <el-descriptions-item label="LLM模型">{{ detail.llm_model_used || '-' }}</el-descriptions-item>
          </el-descriptions>

          <h4 style="margin: 16px 0 8px">摘要</h4>
          <p>{{ detail.summary || '暂无摘要' }}</p>
          <p v-if="detail.summary_zh" style="color: #666; margin-top: 8px">{{ detail.summary_zh }}</p>

          <h4 style="margin: 16px 0 8px">原文内容</h4>
          <div class="content-box">{{ detail.content }}</div>
        </el-card>

        <el-card header="AI 分析" style="margin-top: 16px" v-if="detail.llm_comment">
          <p>{{ detail.llm_comment }}</p>
          <h4 style="margin: 12px 0 8px">建议行动</h4>
          <div v-if="detail.llm_action">{{ detail.llm_action }}</div>
        </el-card>
      </el-col>

      <!-- Right: Scores & Meta -->
      <el-col :span="8">
        <el-card header="评分详情">
          <div class="score-item" v-for="dim in scoreDimensions" :key="dim.key">
            <span class="score-label">{{ dim.label }}</span>
            <el-progress
              :percentage="(detail[dim.key] || 0) * 10"
              :color="scoreColor(detail[dim.key])"
              :format="() => (detail[dim.key] || 0).toFixed(1)"
            />
          </div>
          <el-divider />
          <div class="total-score">
            <span>综合评分</span>
            <span class="total-value">{{ (detail.total_score || 0).toFixed(1) }}</span>
          </div>
        </el-card>

        <el-card header="标签" style="margin-top: 16px">
          <el-tag v-for="tag in (detail.tags || [])" :key="tag" class="tag-item">{{ tag }}</el-tag>
          <span v-if="!detail.tags?.length" style="color: #999">无标签</span>
        </el-card>

        <el-card header="ATT&CK" style="margin-top: 16px">
          <div v-if="detail.mitre_tactics?.length">
            <strong>战术: </strong>
            <el-tag v-for="t in detail.mitre_tactics" :key="t" size="small" class="tag-item">{{ t }}</el-tag>
          </div>
          <div v-if="detail.mitre_techniques?.length" style="margin-top: 8px">
            <strong>技术: </strong>
            <el-tag v-for="t in detail.mitre_techniques" :key="t" size="small" type="warning" class="tag-item">{{ t }}</el-tag>
          </div>
          <span v-if="!detail.mitre_tactics?.length && !detail.mitre_techniques?.length" style="color: #999">
            无 ATT&CK 映射
          </span>
        </el-card>

        <el-card style="margin-top: 16px">
          <el-button type="primary" @click="handleReanalyze" :loading="reanalyzing">重新分析</el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getIntelligenceDetail, reanalyzeIntelligence } from '../api'

const route = useRoute()
const loading = ref(true)
const reanalyzing = ref(false)
const detail = ref({})

const scoreDimensions = [
  { key: 'score_relevance', label: '相关性' },
  { key: 'score_severity', label: '严重性' },
  { key: 'score_timeliness', label: '时效性' },
  { key: 'score_actionability', label: '可操作性' },
  { key: 'score_quality', label: '信息质量' },
]

const priorityTagType = (p) => ({ P0: 'danger', P1: 'warning', P2: '', P3: 'info' }[p] || '')
const tlpType = (t) => ({ RED: 'danger', AMBER: 'warning', GREEN: 'success', CLEAR: 'info' }[t] || '')
const scoreColor = (v) => {
  if (!v) return '#909399'
  if (v >= 8) return '#F56C6C'
  if (v >= 6) return '#E6A23C'
  return '#409EFF'
}

const handleReanalyze = async () => {
  reanalyzing.value = true
  try {
    await reanalyzeIntelligence(route.params.id)
    ElMessage.success('已提交重新分析')
  } catch {
    ElMessage.error('提交失败')
  } finally {
    reanalyzing.value = false
  }
}

onMounted(async () => {
  try {
    detail.value = await getIntelligenceDetail(route.params.id)
  } catch {
    ElMessage.error('加载情报详情失败')
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.content-box {
  max-height: 400px;
  overflow-y: auto;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 4px;
  white-space: pre-wrap;
  font-size: 13px;
  line-height: 1.6;
}
.score-item {
  margin-bottom: 12px;
}
.score-label {
  font-size: 13px;
  color: #606266;
  margin-bottom: 4px;
  display: block;
}
.total-score {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 16px;
  font-weight: bold;
}
.total-value {
  font-size: 24px;
  color: #409EFF;
}
.tag-item {
  margin: 2px 4px 2px 0;
}
</style>
