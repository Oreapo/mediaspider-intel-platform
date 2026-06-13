<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { listDatasets, previewDataset } from '../api/datasets'
import { cancelTaskRun, disableTask, enableTask, getCrawlerDiagnostics, getTask, listTaskRunsPage, startTaskRun } from '../api/tasks'
import AppAlert from '../components/ui/AppAlert.vue'
import BaseSection from '../components/ui/BaseSection.vue'
import EmptyState from '../components/ui/EmptyState.vue'
import LoadingState from '../components/ui/LoadingState.vue'
import PaginationBar from '../components/ui/PaginationBar.vue'
import PermissionGate from '../components/ui/PermissionGate.vue'
import RetryState from '../components/ui/RetryState.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import { useI18n } from '../composables/useI18n'
import { requestConfirm } from '../lib/confirm'
import { lastPageOffset } from '../lib/pagination'
import type { CollectionTask, CrawlerDiagnostics, Dataset, DatasetPreview, TaskRun } from '../types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const taskId = computed(() => String(route.params.taskId || ''))

const task = ref<CollectionTask | null>(null)
const runs = ref<TaskRun[]>([])
const runTotal = ref(0)
const runStatusCounts = ref({ succeeded: 0, failed: 0 })
const runLimit = 10
const runOffset = ref(0)
const datasets = ref<Dataset[]>([])
const diagnostics = ref<CrawlerDiagnostics | null>(null)
const selectedDatasetPreview = ref<DatasetPreview | null>(null)
const selectedDatasetId = ref('')
const isLoading = ref(false)
const runsLoading = ref(false)
const busy = ref(false)
const cancellingRunIds = ref<string[]>([])
const message = ref('')
const error = ref('')
let detailRequestId = 0
let runsRequestId = 0
let previewRequestId = 0

const summaryCards = computed(() => [
  { label: t('taskDetail.runCount'), value: runTotal.value },
  { label: t('taskDetail.succeededRuns'), value: runStatusCounts.value.succeeded },
  { label: t('taskDetail.failedRuns'), value: runStatusCounts.value.failed },
  { label: t('taskDetail.linkedDatasets'), value: datasets.value.length },
])

const runtimeJson = computed(() => JSON.stringify(task.value?.runtime_payload_json || {}, null, 2))
const payloadJson = computed(() => JSON.stringify(task.value?.task_payload_json || {}, null, 2))
const analysisJson = computed(() => JSON.stringify(task.value?.analysis_profile_json || {}, null, 2))

async function loadDetail() {
  const requestedTaskId = taskId.value
  if (!requestedTaskId) return
  const requestId = ++detailRequestId
  const runRequestId = ++runsRequestId
  isLoading.value = true
  error.value = ''
  try {
    const [taskItem, runPage, datasetItems] = await Promise.all([
      getTask(requestedTaskId),
      listTaskRunsPage(requestedTaskId, runLimit, runOffset.value),
      listDatasets({ source_task_id: requestedTaskId }),
    ])
    if (requestId !== detailRequestId || requestedTaskId !== taskId.value) return
    task.value = taskItem
    datasets.value = datasetItems
    if (runRequestId === runsRequestId) {
      runs.value = runPage.runs
      runTotal.value = runPage.total
      runStatusCounts.value = runPage.status_counts
      const normalizedOffset = lastPageOffset(runTotal.value, runLimit)
      if (runOffset.value > normalizedOffset) {
        runOffset.value = normalizedOffset
        if (runTotal.value > 0) await loadRuns()
      }
    }
  } catch (err) {
    if (requestId === detailRequestId && requestedTaskId === taskId.value) {
      error.value = err instanceof Error ? err.message : String(err)
    }
  } finally {
    if (requestId === detailRequestId) {
      isLoading.value = false
    }
  }
}

async function loadRuns(offset = runOffset.value) {
  const requestedTaskId = taskId.value
  if (!requestedTaskId) return
  const requestId = ++runsRequestId
  runsLoading.value = true
  error.value = ''
  try {
    const runPage = await listTaskRunsPage(requestedTaskId, runLimit, offset)
    if (requestId !== runsRequestId || requestedTaskId !== taskId.value) return
    runs.value = runPage.runs
    runTotal.value = runPage.total
    runStatusCounts.value = runPage.status_counts
    runOffset.value = offset
  } catch (err) {
    if (requestId === runsRequestId && requestedTaskId === taskId.value) {
      error.value = err instanceof Error ? err.message : String(err)
    }
  } finally {
    if (requestId === runsRequestId) {
      runsLoading.value = false
    }
  }
}

async function runNow() {
  if (!task.value) return
  busy.value = true
  message.value = ''
  error.value = ''
  try {
    const run = await startTaskRun(task.value.id)
    message.value =
      run.status === 'succeeded'
        ? t('tasks.runCompleted')
        : t('tasks.runStatus', { status: labelValue(run.status) })
    runOffset.value = 0
    await loadDetail()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function toggleStatus(nextStatus: 'enabled' | 'disabled') {
  if (!task.value) return
  busy.value = true
  message.value = ''
  error.value = ''
  try {
    task.value = nextStatus === 'enabled' ? await enableTask(task.value.id) : await disableTask(task.value.id)
    message.value = nextStatus === 'enabled' ? t('tasks.enabledMessage') : t('tasks.disabledMessage')
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function cancelRun(run: TaskRun) {
  if (!task.value || run.status !== 'pending') return
  const confirmed = await requestConfirm({
    title: t('taskDetail.cancelRunTitle'),
    message: t('taskDetail.cancelRunMessage'),
    confirmLabel: t('taskDetail.cancelRunConfirm'),
    tone: 'warning',
  })
  if (!confirmed) return

  cancellingRunIds.value = [...cancellingRunIds.value, run.id]
  message.value = ''
  error.value = ''
  try {
    await cancelTaskRun(task.value.id, run.id)
    message.value = t('taskDetail.runCancelled')
    await loadRuns()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    cancellingRunIds.value = cancellingRunIds.value.filter((id) => id !== run.id)
  }
}

async function diagnose() {
  if (!task.value) return
  busy.value = true
  message.value = ''
  error.value = ''
  try {
    diagnostics.value = await getCrawlerDiagnostics(task.value.id)
    message.value = diagnostics.value.ready ? t('tasks.diagnosticsReady') : t('tasks.diagnosticsBlocked')
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function openDataset(datasetId: string) {
  const requestId = ++previewRequestId
  const requestedTaskId = taskId.value
  selectedDatasetId.value = datasetId
  selectedDatasetPreview.value = null
  error.value = ''
  try {
    const datasetPreview = await previewDataset(datasetId, 20)
    if (requestId === previewRequestId && requestedTaskId === taskId.value) {
      selectedDatasetPreview.value = datasetPreview
    }
  } catch (err) {
    if (requestId === previewRequestId && requestedTaskId === taskId.value) {
      error.value = err instanceof Error ? err.message : String(err)
    }
  }
}

function statusTone(status: string) {
  if (['enabled', 'succeeded', 'ready'].includes(status)) return 'success'
  if (['running', 'draft'].includes(status)) return 'info'
  if (['failed', 'blocked'].includes(status)) return 'danger'
  return 'neutral'
}

function labelValue(value: string) {
  const key = `enum.${value}`
  const translated = t(key)
  return translated === key ? value : translated
}

watch(
  taskId,
  () => {
    runsRequestId += 1
    previewRequestId += 1
    task.value = null
    runs.value = []
    runTotal.value = 0
    runStatusCounts.value = { succeeded: 0, failed: 0 }
    runOffset.value = 0
    datasets.value = []
    diagnostics.value = null
    selectedDatasetPreview.value = null
    selectedDatasetId.value = ''
    message.value = ''
    void loadDetail()
  },
  { immediate: true },
)
</script>

<template>
  <section class="page-grid">
    <button class="secondary-button back-button" type="button" @click="router.push({ name: 'tasks' })">
      {{ t('taskDetail.backToList') }}
    </button>

    <BaseSection v-if="isLoading" compact>
      <LoadingState :title="t('taskDetail.loading')" />
    </BaseSection>
    <BaseSection v-else-if="error && !task" compact>
      <RetryState
        :title="t('taskDetail.loadFailed')"
        :message="error"
        :secondary-label="t('taskDetail.backToList')"
        @retry="loadDetail"
        @secondary="router.push({ name: 'tasks' })"
      />
    </BaseSection>

    <template v-else-if="task">
      <section class="surface hero-panel">
        <div>
          <p class="eyebrow">{{ task.platform }} · {{ task.scenario_type }} · {{ task.task_mode }}</p>
          <h1>{{ task.task_name }}</h1>
          <p>{{ task.notes || t('tasks.noNotes') }}</p>
        </div>
        <div class="hero-actions">
          <StatusBadge :label="labelValue(task.status)" :tone="statusTone(task.status)" />
          <PermissionGate area="operations" compact>
          <button class="secondary-button" :disabled="busy" type="button" @click="toggleStatus('enabled')">{{ t('tasks.enable') }}</button>
          <button class="secondary-button" :disabled="busy" type="button" @click="toggleStatus('disabled')">{{ t('tasks.disable') }}</button>
          <button class="secondary-button" :disabled="busy" type="button" @click="diagnose">{{ t('tasks.diagnoseCrawler') }}</button>
          <button class="primary-button" :disabled="busy" type="button" @click="runNow">
            {{ busy ? t('taskDetail.processing') : t('tasks.startRun') }}
          </button>
          </PermissionGate>
        </div>
      </section>

      <div class="stats-grid">
        <article v-for="item in summaryCards" :key="item.label" class="surface stat-card">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </article>
      </div>

      <AppAlert v-if="message" tone="success" :title="t('tasks.successTitle')" :message="message" />
      <AppAlert v-if="error" tone="error" :title="t('tasks.actionFailedTitle')" :message="error" />

      <div class="split-grid">
        <BaseSection :title="t('taskDetail.configTitle')" :description="`ID: ${task.id} · Auth Profile: ${task.auth_profile_id || '-'}`">
          <div class="config-grid">
            <div>
              <h3>{{ t('taskDetail.collectionTarget') }}</h3>
              <pre>{{ payloadJson }}</pre>
            </div>
            <div>
              <h3>{{ t('taskDetail.runtimeParams') }}</h3>
              <pre>{{ runtimeJson }}</pre>
            </div>
            <div>
              <h3>{{ t('taskDetail.analysisConfig') }}</h3>
              <pre>{{ analysisJson }}</pre>
            </div>
          </div>
        </BaseSection>

        <BaseSection :title="t('taskDetail.diagnosticsTitle')" :description="t('taskDetail.diagnosticsDescription')">
          <div v-if="diagnostics" class="diagnostics-panel">
            <div class="diagnostics-head">
              <StatusBadge :label="diagnostics.ready ? t('tasks.ready') : t('tasks.blocked')" :tone="diagnostics.ready ? 'success' : 'danger'" />
              <span>{{ diagnostics.media_crawler_root || '-' }}</span>
            </div>
            <pre>{{ diagnostics.command.join(' ') }}</pre>
            <div v-if="diagnostics.errors.length" class="error-text">{{ diagnostics.errors.join(' · ') }}</div>
            <div v-if="diagnostics.warnings.length" class="muted">{{ diagnostics.warnings.join(' · ') }}</div>
          </div>
          <EmptyState v-else :title="t('taskDetail.noDiagnosticsTitle')" :description="t('taskDetail.noDiagnosticsDescription')" />
        </BaseSection>
      </div>

      <div class="split-grid">
        <BaseSection :title="t('taskDetail.runRecordsTitle')" :description="t('taskDetail.runRecordsDescription')">
          <div class="item-list">
            <article v-for="run in runs" :key="run.id" class="list-item">
              <div class="item-main">
                <div>
                  <strong>{{ run.id }}</strong>
                  <p>{{ run.trigger_type }} · {{ run.started_at || '-' }}</p>
                </div>
                <div class="run-actions">
                  <StatusBadge :label="labelValue(run.status)" :tone="statusTone(run.status)" />
                  <PermissionGate v-if="run.status === 'pending'" area="operations" compact>
                    <button
                      class="secondary-button"
                      :disabled="cancellingRunIds.includes(run.id)"
                      type="button"
                      @click="cancelRun(run)"
                    >
                      {{ cancellingRunIds.includes(run.id) ? t('taskDetail.cancellingRun') : t('taskDetail.cancelRun') }}
                    </button>
                  </PermissionGate>
                </div>
              </div>
              <div class="item-meta">
                <span>{{ t('taskDetail.finishedAt') }}: {{ run.finished_at || '-' }}</span>
                <span>{{ t('taskDetail.datasets') }}: {{ run.result_dataset_ids.join(', ') || '-' }}</span>
                <span v-if="run.error_message" class="error-text">{{ run.error_message }}</span>
              </div>
            </article>
            <EmptyState v-if="!runs.length" :title="t('taskDetail.noRunsTitle')" :description="t('taskDetail.noRunsDescription')" />
          </div>
          <PaginationBar
            :total="runTotal"
            :limit="runLimit"
            :offset="runOffset"
            :loading="isLoading || runsLoading"
            @change="loadRuns"
          />
        </BaseSection>

        <BaseSection :title="t('taskDetail.linkedDatasets')" :description="t('taskDetail.linkedDatasetsDescription')">
          <div class="dataset-list">
            <button
              v-for="dataset in datasets"
              :key="dataset.id"
              class="dataset-button"
              :class="{ active: selectedDatasetId === dataset.id }"
              type="button"
              @click="openDataset(dataset.id)"
            >
              <strong>{{ dataset.dataset_name }}</strong>
              <span>{{ t('datasets.recordCount', { count: dataset.record_count }) }} · {{ dataset.storage_uri || '-' }}</span>
            </button>
            <EmptyState v-if="!datasets.length" :title="t('taskDetail.noDatasetsTitle')" :description="t('taskDetail.noDatasetsDescription')" />
          </div>
          <div v-if="selectedDatasetPreview" class="preview-box">
            <table>
              <thead>
                <tr>
                  <th v-for="column in selectedDatasetPreview.columns" :key="column">{{ column }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, rowIndex) in selectedDatasetPreview.rows" :key="rowIndex">
                  <td v-for="(cell, cellIndex) in row" :key="cellIndex">{{ cell }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </BaseSection>
      </div>
    </template>
  </section>
</template>

<style scoped>
.page-grid {
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
  align-items: flex-start;
}

.eyebrow,
.section-head p,
.muted,
.item-main p,
.item-meta,
.dataset-button span,
.stat-card span {
  color: #64748b;
}

.hero-panel h1 {
  margin: 6px 0;
  font-size: 32px;
  letter-spacing: 0;
}

.hero-actions,
.diagnostics-head,
.run-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  justify-content: flex-end;
}

.stats-grid,
.split-grid,
.config-grid {
  display: grid;
  gap: 18px;
}

.stats-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.split-grid {
  grid-template-columns: 1fr 1fr;
}

.config-grid {
  grid-template-columns: 1fr;
}

.stat-card strong {
  display: block;
  margin-top: 6px;
  font-size: 32px;
}

.section-head {
  margin-bottom: 16px;
}

.section-head h2,
.config-grid h3 {
  margin: 0 0 6px;
}

.item-list,
.dataset-list {
  display: grid;
  gap: 12px;
}

.list-item,
.diagnostics-panel,
.preview-box {
  padding: 14px;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(248, 250, 252, 0.82);
}

.item-main {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.item-meta {
  display: grid;
  gap: 5px;
  margin-top: 10px;
  font-size: 13px;
}

.dataset-button {
  display: grid;
  gap: 4px;
  width: 100%;
  padding: 14px;
  text-align: left;
  border-radius: 14px;
  border: 1px solid rgba(203, 213, 225, 0.9);
  background: rgba(255, 255, 255, 0.82);
  cursor: pointer;
}

.dataset-button.active {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

pre {
  margin: 0;
  padding: 12px;
  overflow: auto;
  border-radius: 12px;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 12px;
}

.preview-box {
  margin-top: 14px;
  overflow: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

th,
td {
  max-width: 260px;
  padding: 10px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.9);
  text-align: left;
  vertical-align: top;
  overflow-wrap: anywhere;
}

th {
  color: #334155;
  background: rgba(241, 245, 249, 0.9);
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

.back-button {
  justify-self: start;
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

.success-text {
  color: #15803d;
}

.error-text {
  color: #dc2626;
}

@media (max-width: 980px) {
  .hero-panel,
  .split-grid,
  .stats-grid {
    grid-template-columns: 1fr;
    display: grid;
  }

  .hero-actions {
    justify-content: start;
  }
}
</style>
