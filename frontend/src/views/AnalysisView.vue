<script setup lang="ts">
import { computed, ref } from 'vue'
import { createAnalysisJob, getAnalysisOutputs } from '../api/analysis'
import AppAlert from '../components/ui/AppAlert.vue'
import AppSelect from '../components/ui/AppSelect.vue'
import BaseSection from '../components/ui/BaseSection.vue'
import EmptyState from '../components/ui/EmptyState.vue'
import FieldError from '../components/ui/FieldError.vue'
import LoadingState from '../components/ui/LoadingState.vue'
import PaginationBar from '../components/ui/PaginationBar.vue'
import PermissionGate from '../components/ui/PermissionGate.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import { useAnalysisJobs } from '../composables/useAnalysisJobs'
import { useDatasets } from '../composables/useDatasets'
import { useI18n } from '../composables/useI18n'
import { enumLabel as labelValue } from '../composables/useEnumLabel'
import { lastPageOffset } from '../lib/pagination'
import { parseJsonObject, required, type ValidationErrors } from '../lib/validation'
import type { AnalysisOutput } from '../types'

const { t } = useI18n()
const jobLimit = 12
const jobOffset = ref(0)
const {
  items: jobItems,
  total: jobTotal,
  isLoading: jobsLoading,
  error: jobsError,
  fetchItems: fetchJobs,
} = useAnalysisJobs({ limit: jobLimit, offset: 0 })
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
const fieldErrors = ref<ValidationErrors>({})

const selectedJob = computed(() => jobItems.value.find((item) => item.id === selectedJobId.value))
const analysisStats = computed(() => [
  { label: t('analysis.jobsTitle'), value: jobTotal.value },
  { label: t('enum.succeeded'), value: jobItems.value.filter((item) => item.status === 'succeeded').length },
  { label: t('enum.running'), value: jobItems.value.filter((item) => item.status === 'running').length },
  { label: t('analysis.outputsTitle'), value: outputs.value.length },
])

async function fetchJobPage(offset = jobOffset.value) {
  jobOffset.value = offset
  await fetchJobs({ limit: jobLimit, offset })
  const normalizedOffset = lastPageOffset(jobTotal.value, jobLimit)
  if (jobOffset.value > normalizedOffset) {
    jobOffset.value = normalizedOffset
    if (jobTotal.value > 0) {
      await fetchJobs({ limit: jobLimit, offset: normalizedOffset })
    }
  }
}

async function changeJobPage(offset: number) {
  selectedJobId.value = ''
  outputs.value = []
  await fetchJobPage(offset)
}

function validateAnalysisForm() {
  const errors: ValidationErrors = {}
  const datasetError = required(form.value.dataset_id, t('analysis.dataset'))
  const typeError = required(form.value.analysis_type, t('analysis.type'))
  const parameters = parseJsonObject(form.value.parameters_json, t('analysis.parametersJson'))

  if (datasetError) errors.dataset_id = datasetError
  if (typeError) errors.analysis_type = typeError
  if (parameters.error) errors.parameters_json = parameters.error

  fieldErrors.value = errors
  return {
    isValid: Object.keys(errors).length === 0,
    parameters: parameters.value || {},
  }
}

async function submitAnalysisJob() {
  message.value = ''
  error.value = ''
  const validation = validateAnalysisForm()
  if (!validation.isValid) {
    error.value = t('analysis.fixFormErrors')
    return
  }

  creating.value = true
  try {
    const job = await createAnalysisJob({
      dataset_id: form.value.dataset_id,
      analysis_scope: form.value.analysis_scope,
      analysis_type: form.value.analysis_type,
      parameters_json: validation.parameters,
    })
    message.value = t('analysis.createdMessage')
    selectedJobId.value = job.id
    await fetchJobPage(0)
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

function jobTone(status: string) {
  if (status === 'succeeded' || status === 'completed') return 'success'
  if (status === 'running') return 'info'
  if (status === 'failed') return 'danger'
  return 'neutral'
}

function scopeLabel(value: string) {
  const key = `analysisScope.${value}`
  const translated = t(key)
  return translated === key ? value : translated
}
</script>

<template>
  <section class="page-grid">
    <div class="stats-grid">
      <article v-for="stat in analysisStats" :key="stat.label" class="surface stat-card">
        <span>{{ stat.label }}</span>
        <strong>{{ stat.value }}</strong>
      </article>
    </div>

    <div class="analysis-workspace">
      <aside class="analysis-side-panel">
        <BaseSection compact :title="t('analysis.createTitle')" :description="t('analysis.createDescription')">
          <PermissionGate area="analysis">
            <form class="analysis-form" @submit.prevent="submitAnalysisJob">
              <div class="grid-two">
                <label class="field">
                  <span>{{ t('analysis.dataset') }}</span>
                  <AppSelect
                    v-model="form.dataset_id"
                    :placeholder="t('analysis.selectDataset')"
                    :options="datasetItems.map((item) => ({
                      value: item.id,
                      label: `${item.dataset_name} · ${item.source_platform}`,
                    }))"
                  />
                  <FieldError :message="fieldErrors.dataset_id" />
                </label>

                <label class="field">
                  <span>{{ t('analysis.scope') }}</span>
                  <AppSelect
                    v-model="form.analysis_scope"
                    :options="[
                      { value: 'common', label: t('analysisScope.common') },
                      { value: 'platform', label: t('analysisScope.platform') },
                      { value: 'cross_platform', label: t('analysisScope.cross_platform') },
                    ]"
                  />
                </label>
              </div>

              <div class="grid-two">
                <label class="field">
                  <span>{{ t('analysis.type') }}</span>
                  <input v-model="form.analysis_type" required placeholder="summary / topic_map / seller_profile" />
                  <FieldError :message="fieldErrors.analysis_type" />
                </label>

                <label class="field">
                  <span>{{ t('analysis.parametersJson') }}</span>
                  <input v-model="form.parameters_json" placeholder='{"window":"last_30_days"}' />
                  <FieldError :message="fieldErrors.parameters_json" />
                </label>
              </div>

              <div class="actions">
                <button class="primary-button" :disabled="creating" type="submit">
                  {{ creating ? t('analysis.creating') : t('analysis.create') }}
                </button>
              </div>
            </form>
          </PermissionGate>
        </BaseSection>

        <AppAlert v-if="message" tone="success" :title="t('analysis.operationSuccess')" :message="message" />
        <AppAlert v-if="error" tone="error" :title="t('analysis.operationFailed')" :message="error" />
      </aside>

      <main class="analysis-main-panel">
        <div class="split-grid">
          <BaseSection :title="t('analysis.jobsTitle')" :description="t('analysis.jobsDescription')">
            <LoadingState v-if="jobsLoading" :title="t('analysis.loadingJobs')" />
            <AppAlert v-else-if="jobsError" tone="error" :title="t('common.loadFailed')" :message="jobsError" />
            <div v-else class="job-list">
              <article v-for="item in jobItems" :key="item.id" class="job-item">
                <div class="job-main">
                  <div>
                    <strong>{{ item.analysis_type }}</strong>
                    <p>{{ scopeLabel(item.analysis_scope) }} · {{ labelValue(item.status) }} · {{ item.dataset_id }}</p>
                  </div>
                  <StatusBadge :label="labelValue(item.status)" :tone="jobTone(item.status)" />
                </div>
                <code class="job-id">{{ item.id }}</code>
                <div class="job-meta">
                  <span>{{ t('analysis.startedAt') }}: {{ item.started_at || '-' }}</span>
                  <span>{{ t('analysis.finishedAt') }}: {{ item.finished_at || '-' }}</span>
                </div>
                <div class="actions">
                  <button class="secondary-button" type="button" @click="openOutputs(item.id)">{{ t('analysis.viewOutputs') }}</button>
                </div>
              </article>
              <EmptyState v-if="!jobItems.length" :title="t('analysis.noJobsTitle')" :description="t('analysis.noJobsDescription')" />
              <PaginationBar
                :total="jobTotal"
                :limit="jobLimit"
                :offset="jobOffset"
                :loading="jobsLoading"
                @change="changeJobPage"
              />
            </div>
          </BaseSection>

          <BaseSection :title="t('analysis.outputsTitle')" :description="selectedJob ? `${selectedJob.analysis_type} · ${selectedJob.dataset_id}` : t('analysis.outputsDescription')">
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
            <EmptyState v-else :title="t('analysis.noOutputsTitle')" :description="t('analysis.noOutputsDescription')" />
          </BaseSection>
        </div>
      </main>
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

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.analysis-workspace {
  display: grid;
  grid-template-columns: minmax(320px, 390px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.analysis-side-panel {
  position: sticky;
  top: 86px;
  max-height: calc(100vh - 104px);
  min-width: 0;
  display: grid;
  gap: 14px;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding-right: 2px;
}

.analysis-main-panel {
  min-width: 0;
}

.analysis-side-panel .grid-two {
  grid-template-columns: 1fr;
}

.analysis-side-panel .actions {
  display: grid;
}

.analysis-side-panel .primary-button,
.analysis-side-panel .secondary-button {
  width: 100%;
}

.section-card {
  border-radius: 24px;
  padding: 22px;
}

.stat-card {
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
.stat-card span,
.job-item p,
.job-meta,
.output-summary,
.summary-card span {
  color: #64748b;
}

.stat-card strong {
  display: block;
  margin-top: 6px;
  font-size: 34px;
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
  background: linear-gradient(135deg, #2563eb 0%, var(--primary) 100%);
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
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .analysis-workspace {
    grid-template-columns: 1fr;
  }

  .analysis-side-panel {
    position: static;
    max-height: none;
    overflow: visible;
    padding-right: 0;
  }

  .split-grid,
  .grid-two,
  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
