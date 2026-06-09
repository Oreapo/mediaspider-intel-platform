<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getAnalysisOutputs, listAnalysisJobs } from '../api/analysis'
import { getDataset, previewDataset } from '../api/datasets'
import { getTask, listTaskRuns } from '../api/tasks'
import AppAlert from '../components/ui/AppAlert.vue'
import BaseSection from '../components/ui/BaseSection.vue'
import EmptyState from '../components/ui/EmptyState.vue'
import LoadingState from '../components/ui/LoadingState.vue'
import RetryState from '../components/ui/RetryState.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import { useI18n } from '../composables/useI18n'
import type { AnalysisJob, AnalysisOutput, CollectionTask, Dataset, DatasetPreview, TaskRun } from '../types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const datasetId = computed(() => String(route.params.datasetId || ''))

const dataset = ref<Dataset | null>(null)
const sourceTask = ref<CollectionTask | null>(null)
const sourceRuns = ref<TaskRun[]>([])
const preview = ref<DatasetPreview | null>(null)
const analysisJobs = ref<AnalysisJob[]>([])
const analysisOutputs = ref<Record<string, AnalysisOutput[]>>({})
const isLoading = ref(false)
const error = ref('')

const summaryCards = computed(() => [
  { label: t('datasetDetail.records'), value: dataset.value?.record_count || 0 },
  { label: t('datasetDetail.analysisJobs'), value: analysisJobs.value.length },
  { label: t('datasetDetail.outputs'), value: Object.values(analysisOutputs.value).flat().length },
  { label: t('datasetDetail.sourceRuns'), value: dataset.value?.source_run_id ? 1 : 0 },
])

async function loadDetail() {
  if (!datasetId.value) return
  isLoading.value = true
  error.value = ''
  try {
    const datasetItem = await getDataset(datasetId.value)
    dataset.value = datasetItem
    const [previewData, jobs] = await Promise.all([previewDataset(datasetId.value, 50), listAnalysisJobs()])
    preview.value = previewData
    analysisJobs.value = jobs.filter((job) => job.dataset_id === datasetId.value)
    const outputEntries = await Promise.all(
      analysisJobs.value.map(async (job) => {
        try {
          return [job.id, await getAnalysisOutputs(job.id)] as const
        } catch {
          return [job.id, []] as const
        }
      }),
    )
    analysisOutputs.value = Object.fromEntries(outputEntries)
    if (datasetItem.source_task_id) {
      sourceTask.value = await getTask(datasetItem.source_task_id)
      sourceRuns.value = await listTaskRuns(datasetItem.source_task_id)
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    isLoading.value = false
  }
}

function runStatus(runId: string | null) {
  if (!runId) return null
  return sourceRuns.value.find((run) => run.id === runId) || null
}

function jobTone(status: string) {
  if (['succeeded', 'completed'].includes(status)) return 'success'
  if (status === 'running') return 'info'
  if (status === 'failed') return 'danger'
  return 'neutral'
}

function labelValue(value: string) {
  const key = `enum.${value}`
  const translated = t(key)
  return translated === key ? value : translated
}

function scopeLabel(value: string) {
  const key = `analysisScope.${value}`
  const translated = t(key)
  return translated === key ? value : translated
}

onMounted(loadDetail)
</script>

<template>
  <section class="page-grid">
    <button class="secondary-button back-button" type="button" @click="router.push({ name: 'datasets' })">
      {{ t('datasetDetail.backToList') }}
    </button>

    <BaseSection v-if="isLoading" compact>
      <LoadingState :title="t('datasetDetail.loading')" />
    </BaseSection>
    <BaseSection v-else-if="error && !dataset" compact>
      <RetryState
        :title="t('datasetDetail.loadFailed')"
        :message="error"
        :secondary-label="t('datasetDetail.backToList')"
        @retry="loadDetail"
        @secondary="router.push({ name: 'datasets' })"
      />
    </BaseSection>

    <template v-else-if="dataset">
      <section class="surface hero-panel">
        <div>
          <p class="eyebrow">{{ dataset.source_platform }} · {{ dataset.scenario_type || '-' }} · {{ dataset.dataset_type }}</p>
          <h1>{{ dataset.dataset_name }}</h1>
          <p>{{ dataset.storage_uri || t('datasetDetail.noStoragePath') }}</p>
        </div>
        <div class="hero-side">
          <span class="status-badge">{{ dataset.id }}</span>
          <span>{{ dataset.snapshot_time || dataset.created_at }}</span>
        </div>
      </section>

      <div class="stats-grid">
        <article v-for="item in summaryCards" :key="item.label" class="surface stat-card">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </article>
      </div>

      <AppAlert v-if="error" tone="error" :title="t('datasetDetail.partialLoadFailed')" :message="error" />

      <div class="split-grid">
        <BaseSection :title="t('datasetDetail.sourceTraceTitle')" :description="t('datasetDetail.sourceTraceDescription')">
          <div class="trace-grid">
            <div class="trace-card">
              <span>{{ t('datasetDetail.sourceTask') }}</span>
              <strong>{{ sourceTask?.task_name || dataset.source_task_id || '-' }}</strong>
              <RouterLink
                v-if="dataset.source_task_id"
                class="secondary-button link-button"
                :to="{ name: 'task-detail', params: { taskId: dataset.source_task_id } }"
              >
                {{ t('datasetDetail.openTask') }}
              </RouterLink>
            </div>
            <div class="trace-card">
              <span>{{ t('datasetDetail.sourceRun') }}</span>
              <strong>{{ dataset.source_run_id || '-' }}</strong>
              <p v-if="runStatus(dataset.source_run_id)">{{ t('tasks.status') }}: {{ labelValue(runStatus(dataset.source_run_id)?.status || '') }}</p>
            </div>
            <div class="trace-card">
              <span>{{ t('datasets.tags') }}</span>
              <strong>{{ dataset.tags.join(', ') || '-' }}</strong>
            </div>
          </div>
        </BaseSection>

        <BaseSection :title="t('analysis.outputsTitle')" :description="t('datasetDetail.analysisDescription')">
          <div class="item-list">
            <article v-for="job in analysisJobs" :key="job.id" class="list-item">
              <div class="item-main">
                <div>
                  <strong>{{ job.analysis_type }}</strong>
                  <p>{{ scopeLabel(job.analysis_scope) }} · {{ job.created_at }}</p>
                </div>
                <StatusBadge :label="labelValue(job.status)" :tone="jobTone(job.status)" />
              </div>
              <div v-for="output in analysisOutputs[job.id] || []" :key="output.id" class="output-card">
                <strong>{{ output.title }}</strong>
                <p>{{ output.summary }}</p>
              </div>
            </article>
            <EmptyState v-if="!analysisJobs.length" :title="t('analysis.noJobsTitle')" :description="t('datasetDetail.noAnalysisDescription')" />
          </div>
        </BaseSection>
      </div>

      <BaseSection :title="t('datasetDetail.previewTitle')" :description="t('datasetDetail.previewDescription')">
        <div v-if="preview?.columns.length" class="preview-wrap">
          <table>
            <thead>
              <tr>
                <th v-for="column in preview.columns" :key="column">{{ column }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, rowIndex) in preview.rows" :key="rowIndex">
                <td v-for="(cell, cellIndex) in row" :key="cellIndex">{{ cell }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <EmptyState v-else :title="t('datasets.previewEmptyTitle')" :description="t('datasetDetail.previewEmptyDescription')" />
      </BaseSection>
    </template>
  </section>
</template>

<style scoped>
.page-grid,
.item-list {
  display: grid;
  gap: 18px;
}

.hero-panel,
.section-card,
.stat-card {
  border-radius: 24px;
  padding: 22px;
}

.hero-panel {
  display: flex;
  justify-content: space-between;
  gap: 18px;
}

.hero-panel h1 {
  margin: 6px 0;
  font-size: 32px;
  letter-spacing: 0;
}

.hero-side {
  display: grid;
  gap: 8px;
  justify-items: end;
  color: #64748b;
  font-weight: 700;
}

.eyebrow,
.section-head p,
.muted,
.trace-card span,
.trace-card p,
.item-main p,
.output-card p,
.stat-card span {
  color: #64748b;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 18px;
}

.split-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
}

.trace-grid {
  display: grid;
  gap: 12px;
}

.trace-card,
.list-item,
.output-card {
  display: grid;
  gap: 8px;
  padding: 14px;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(248, 250, 252, 0.82);
}

.stat-card strong {
  display: block;
  margin-top: 6px;
  font-size: 32px;
}

.section-head {
  margin-bottom: 16px;
}

.section-head h2 {
  margin: 0 0 6px;
}

.item-main {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.item-main p,
.output-card p {
  margin: 0;
}

.preview-wrap {
  overflow: auto;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.9);
}

table {
  width: 100%;
  min-width: 760px;
  border-collapse: collapse;
  font-size: 13px;
}

th,
td {
  max-width: 280px;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.8);
  text-align: left;
  vertical-align: top;
  overflow-wrap: anywhere;
}

th {
  background: rgba(241, 245, 249, 0.92);
}

.primary-button,
.secondary-button {
  border: none;
  border-radius: 12px;
  padding: 10px 14px;
  font-weight: 700;
  cursor: pointer;
}

.secondary-button {
  background: rgba(226, 232, 240, 0.9);
  color: #1e293b;
}

.back-button {
  justify-self: start;
}

.link-button {
  justify-self: start;
  text-decoration: none;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 6px 10px;
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.status-badge.failed {
  background: rgba(239, 68, 68, 0.12);
  color: #b91c1c;
}

.error-text {
  color: #dc2626;
}

@media (max-width: 980px) {
  .hero-panel,
  .split-grid,
  .stats-grid {
    display: grid;
    grid-template-columns: 1fr;
  }

  .hero-side {
    justify-items: start;
  }
}
</style>
