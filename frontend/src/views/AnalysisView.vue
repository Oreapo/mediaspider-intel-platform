<script setup lang="ts">
import { computed, ref } from 'vue'
import { createAnalysisJob, getAnalysisOutputs } from '../api/analysis'
import { useAnalysisJobs } from '../composables/useAnalysisJobs'
import { useDatasets } from '../composables/useDatasets'
import type { AnalysisOutput } from '../types'

const {
  items: jobItems,
  isLoading: jobsLoading,
  error: jobsError,
  fetchItems: fetchJobs,
} = useAnalysisJobs()
const { items: datasetItems } = useDatasets()

const form = ref({
  dataset_id: '',
  analysis_scope: 'common',
  analysis_type: 'summary',
  parameters_json: '{"window":"last_30_days"}',
})
const outputs = ref<AnalysisOutput[]>([])
const selectedJobId = ref('')
const creating = ref(false)
const message = ref('')
const error = ref('')

const selectedJob = computed(() => jobItems.value.find((item) => item.id === selectedJobId.value))

async function submitAnalysisJob() {
  creating.value = true
  message.value = ''
  error.value = ''
  try {
    const parameters = form.value.parameters_json.trim()
      ? JSON.parse(form.value.parameters_json)
      : {}
    const job = await createAnalysisJob({
      dataset_id: form.value.dataset_id,
      analysis_scope: form.value.analysis_scope,
      analysis_type: form.value.analysis_type,
      parameters_json: parameters,
    })
    message.value = 'Analysis job created.'
    selectedJobId.value = job.id
    await fetchJobs()
    outputs.value = await getAnalysisOutputs(job.id)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    creating.value = false
  }
}

async function openOutputs(jobId: string) {
  selectedJobId.value = jobId
  message.value = ''
  error.value = ''
  try {
    outputs.value = await getAnalysisOutputs(jobId)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
    outputs.value = []
  }
}

function summaryCards(output: AnalysisOutput) {
  return Array.isArray(output.payload_json.summary_cards)
    ? (output.payload_json.summary_cards as Array<Record<string, unknown>>)
    : []
}

function topTerms(output: AnalysisOutput) {
  return Array.isArray(output.payload_json.top_terms)
    ? (output.payload_json.top_terms as Array<Record<string, unknown>>)
    : []
}
</script>

<template>
  <section class="page-grid">
    <section class="surface section-card">
      <div class="section-head">
        <div>
          <h2>Create Analysis Job</h2>
          <p>先做通用分析入口。后续在这里继续扩展平台专属分析与跨平台分析。</p>
        </div>
      </div>

      <form class="analysis-form" @submit.prevent="submitAnalysisJob">
        <div class="grid-two">
          <label class="field">
            <span>Dataset</span>
            <select v-model="form.dataset_id" required>
              <option value="" disabled>选择一个数据集</option>
              <option v-for="item in datasetItems" :key="item.id" :value="item.id">
                {{ item.dataset_name }} · {{ item.source_platform }}
              </option>
            </select>
          </label>

          <label class="field">
            <span>Analysis Scope</span>
            <select v-model="form.analysis_scope">
              <option value="common">common</option>
              <option value="platform">platform</option>
              <option value="cross_platform">cross_platform</option>
            </select>
          </label>
        </div>

        <div class="grid-two">
          <label class="field">
            <span>Analysis Type</span>
            <input v-model="form.analysis_type" required placeholder="summary / topic_map / seller_profile" />
          </label>

          <label class="field">
            <span>Parameters JSON</span>
            <input v-model="form.parameters_json" placeholder='{"window":"last_30_days"}' />
          </label>
        </div>

        <div class="actions">
          <button class="primary-button" :disabled="creating" type="submit">
            {{ creating ? 'Creating...' : 'Create Analysis Job' }}
          </button>
          <span v-if="message" class="success-text">{{ message }}</span>
          <span v-if="error" class="error-text">{{ error }}</span>
        </div>
      </form>
    </section>

    <div class="split-grid">
      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Analysis Jobs</h2>
            <p>最小闭环先聚焦 dataset -> analysis job -> outputs。</p>
          </div>
        </div>

        <div v-if="jobsLoading" class="muted">Loading analysis jobs...</div>
        <div v-else-if="jobsError" class="error-text">{{ jobsError }}</div>
        <div v-else class="job-list">
          <article v-for="item in jobItems" :key="item.id" class="job-item">
            <div class="job-main">
              <div>
                <strong>{{ item.analysis_type }}</strong>
                <p>{{ item.analysis_scope }} · {{ item.status }} · {{ item.dataset_id }}</p>
              </div>
              <span class="job-id">{{ item.id }}</span>
            </div>
            <div class="job-meta">
              <span>Started: {{ item.started_at || '-' }}</span>
              <span>Finished: {{ item.finished_at || '-' }}</span>
            </div>
            <div class="actions">
              <button class="secondary-button" type="button" @click="openOutputs(item.id)">View Outputs</button>
            </div>
          </article>
          <div v-if="!jobItems.length" class="muted">No analysis jobs yet.</div>
        </div>
      </section>

      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Analysis Outputs</h2>
            <p>{{ selectedJob ? `${selectedJob.analysis_type} · ${selectedJob.dataset_id}` : '选择一个分析任务查看输出。' }}</p>
          </div>
        </div>

        <div v-if="outputs.length" class="output-list">
          <article v-for="output in outputs" :key="output.id" class="output-card">
            <strong>{{ output.title }}</strong>
            <p class="output-summary">{{ output.summary }}</p>

            <div class="summary-grid">
              <div v-for="(card, index) in summaryCards(output)" :key="index" class="summary-card">
                <span>{{ card.label }}</span>
                <strong>{{ card.value }}</strong>
              </div>
            </div>

            <div class="term-list">
              <span v-for="(term, index) in topTerms(output)" :key="index" class="term-chip">
                {{ term.term }} · {{ term.count }}
              </span>
            </div>
          </article>
        </div>
        <div v-else class="muted">No outputs loaded.</div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.page-grid,
.analysis-form,
.job-list,
.output-list {
  display: grid;
  gap: 18px;
}

.split-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
}

.section-card {
  border-radius: 24px;
  padding: 22px;
}

.section-head {
  margin-bottom: 16px;
}

.section-head h2 {
  margin: 0 0 6px;
}

.section-head p,
.muted,
.field span,
.job-item p,
.job-meta,
.output-summary,
.summary-card span {
  color: #64748b;
}

.grid-two {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.field {
  display: grid;
  gap: 8px;
}

.field span {
  font-size: 13px;
  font-weight: 700;
}

.field input,
.field select {
  width: 100%;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid rgba(203, 213, 225, 0.95);
  background: rgba(255, 255, 255, 0.94);
}

.job-item,
.output-card {
  padding: 16px;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(248, 250, 252, 0.82);
}

.job-main {
  display: flex;
  gap: 12px;
  justify-content: space-between;
}

.job-main strong,
.output-card strong {
  display: block;
  margin-bottom: 4px;
}

.job-main p {
  margin: 0;
}

.job-id {
  font-size: 12px;
  color: #2563eb;
  font-weight: 700;
}

.job-meta {
  display: grid;
  gap: 6px;
  margin: 12px 0;
  font-size: 13px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin: 14px 0;
}

.summary-card {
  border-radius: 14px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(226, 232, 240, 0.9);
}

.summary-card strong {
  margin: 6px 0 0;
}

.term-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.term-chip {
  border-radius: 999px;
  padding: 8px 10px;
  background: rgba(59, 130, 246, 0.08);
  color: #1d4ed8;
  font-size: 13px;
  font-weight: 700;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.primary-button,
.secondary-button {
  border: none;
  border-radius: 12px;
  padding: 10px 14px;
  font-weight: 700;
  cursor: pointer;
}

.primary-button {
  background: linear-gradient(135deg, #2563eb 0%, #0f766e 100%);
  color: white;
}

.secondary-button {
  background: rgba(226, 232, 240, 0.9);
  color: #1e293b;
}

.success-text {
  color: #15803d;
}

.error-text {
  color: #dc2626;
}

@media (max-width: 980px) {
  .split-grid,
  .grid-two,
  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
