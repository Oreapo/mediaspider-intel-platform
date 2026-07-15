<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getSignalDetail, updateSignalStatus } from '../api/signals'
import AppAlert from '../components/ui/AppAlert.vue'
import AppIcon from '../components/ui/AppIcon.vue'
import BaseSection from '../components/ui/BaseSection.vue'
import EmptyState from '../components/ui/EmptyState.vue'
import LoadingState from '../components/ui/LoadingState.vue'
import PermissionGate from '../components/ui/PermissionGate.vue'
import RetryState from '../components/ui/RetryState.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import { useI18n } from '../composables/useI18n'
import { useAuth } from '../composables/useAuth'
import { hasRole } from '../lib/permissions'
import { enumLabel as labelValue, scenarioLabel } from '../composables/useEnumLabel'
import type { CaseDetail, CaseRecord, CollectionTask, Dataset, DatasetPreview, Signal, TaskRun } from '../types'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const { user } = useAuth()
const signalId = computed(() => String(route.params.signalId || ''))
const canReveal = computed(() => hasRole(user.value, ['admin']))
const revealed = ref(false)

const signal = ref<Signal | null>(null)
const dataset = ref<Dataset | null>(null)
const sourceTask = ref<CollectionTask | null>(null)
const sourceRun = ref<TaskRun | null>(null)
const preview = ref<DatasetPreview | null>(null)
const linkedCases = ref<CaseRecord[]>([])
const linkedCaseDetails = ref<CaseDetail[]>([])
const isLoading = ref(false)
const busy = ref(false)
const message = ref('')
const error = ref('')

const sourceRef = computed<Record<string, unknown>>(() => {
  const ref = signal.value?.payload_json.source_ref
  return ref && typeof ref === 'object' ? (ref as Record<string, unknown>) : {}
})

const rowIndex = computed(() => {
  const value = sourceRef.value.row_index
  return typeof value === 'number' ? value : null
})

const evidenceFields = computed(() => {
  if (!signal.value) return []
  return Object.entries(signal.value.payload_json)
    .filter(([key]) => key !== 'source_ref')
    .map(([key, value]) => ({
      key,
      value: typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value),
    }))
})

const selectedPreviewRow = computed(() => {
  if (!preview.value || rowIndex.value === null) return null
  return preview.value.rows[rowIndex.value] || null
})

const summaryCards = computed(() => [
  { label: t('signals.riskLevel'), value: signal.value?.risk_level ? labelValue(signal.value.risk_level) : '-', icon: 'alert', color: '#dc4536' },
  { label: t('signals.riskScore'), value: signal.value?.risk_score ?? '-', icon: 'chart', color: 'var(--primary)' },
  { label: t('tasks.status'), value: signal.value?.status ? labelValue(signal.value.status) : '-', icon: 'activity', color: '#cf8214' },
  { label: t('signalDetail.linkedCases'), value: linkedCases.value.length, icon: 'briefcase', color: '#17915a' },
])

async function loadDetail(reveal = false) {
  if (!signalId.value) return
  isLoading.value = true
  error.value = ''
  try {
    const detail = await getSignalDetail(signalId.value, reveal)
    signal.value = detail.signal
    dataset.value = detail.dataset
    preview.value = detail.preview
    sourceTask.value = detail.source_task
    sourceRun.value = detail.source_run
    linkedCases.value = detail.linked_cases
    linkedCaseDetails.value = detail.linked_case_details
    revealed.value = reveal
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    isLoading.value = false
  }
}

async function revealPlaintext() {
  await loadDetail(true)
}

async function setStatus(status: string) {
  if (!signal.value) return
  busy.value = true
  message.value = ''
  error.value = ''
  try {
    signal.value = await updateSignalStatus(signal.value.id, status)
    message.value = t('signals.statusUpdated', { status: labelValue(status) })
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

function riskTone(level: string) {
  if (['critical', 'high'].includes(level)) return 'danger'
  if (level === 'medium') return 'warning'
  if (level === 'low') return 'success'
  return 'neutral'
}

function statusTone(status: string) {
  if (status === 'confirmed') return 'success'
  if (status === 'reviewing') return 'info'
  if (status === 'dismissed') return 'neutral'
  if (status === 'new') return 'warning'
  return 'neutral'
}

onMounted(loadDetail)
</script>

<template>
  <section class="page-grid">
    <button class="secondary-button back-button" type="button" @click="router.push({ name: 'signals' })">
      {{ t('signalDetail.backToQueue') }}
    </button>

    <BaseSection v-if="isLoading" compact>
      <LoadingState :title="t('signalDetail.loading')" />
    </BaseSection>
    <BaseSection v-else-if="error && !signal" compact>
      <RetryState
        :title="t('signalDetail.loadFailed')"
        :message="error"
        :secondary-label="t('signalDetail.backToQueue')"
        @retry="loadDetail"
        @secondary="router.push({ name: 'signals' })"
      />
    </BaseSection>

    <template v-else-if="signal">
      <section class="surface hero-panel">
        <div>
          <p class="eyebrow">{{ labelValue(signal.signal_type) }} · {{ signal.signal_source }} · {{ signal.id }}</p>
          <h1>{{ signal.summary }}</h1>
          <p>{{ t('signals.dataset') }}: {{ signal.dataset_id }} · {{ t('signalDetail.run') }}: {{ signal.task_run_id || '-' }}</p>
        </div>
        <div class="hero-actions">
          <StatusBadge :label="labelValue(signal.risk_level)" :tone="riskTone(signal.risk_level)" />
          <StatusBadge :label="labelValue(signal.status)" :tone="statusTone(signal.status)" />
          <PermissionGate area="analysis" compact>
          <button class="secondary-button" :disabled="busy" type="button" @click="setStatus('reviewing')">{{ t('signals.review') }}</button>
          <button class="secondary-button" :disabled="busy" type="button" @click="setStatus('confirmed')">{{ t('signals.confirm') }}</button>
          <button class="secondary-button" :disabled="busy" type="button" @click="setStatus('dismissed')">{{ t('signals.dismiss') }}</button>
          </PermissionGate>
        </div>
      </section>

      <div class="stats-grid">
        <article
          v-for="item in summaryCards"
          :key="item.label"
          class="surface stat-card"
          :style="{ '--stat-accent': item.color }"
        >
          <div class="stat-top">
            <span>{{ item.label }}</span>
            <span class="stat-icon"><AppIcon :name="item.icon" :size="18" /></span>
          </div>
          <strong>{{ item.value }}</strong>
        </article>
      </div>

      <AppAlert v-if="message" tone="success" :title="t('common.operationSuccess')" :message="message" />
      <AppAlert v-if="error" tone="error" :title="t('tasks.actionFailedTitle')" :message="error" />

      <div class="split-grid">
        <BaseSection :title="t('signals.traceTitle')" :description="t('signalDetail.traceDescription')">
          <div class="trace-grid">
            <div class="trace-card">
              <span>{{ t('signals.dataset') }}</span>
              <strong>{{ dataset?.dataset_name || signal.dataset_id }}</strong>
              <RouterLink class="secondary-button link-button" :to="{ name: 'dataset-detail', params: { datasetId: signal.dataset_id } }">
                {{ t('signalDetail.openDataset') }}
              </RouterLink>
            </div>
            <div class="trace-card">
              <span>{{ t('datasetDetail.sourceTask') }}</span>
              <strong>{{ sourceTask?.task_name || dataset?.source_task_id || '-' }}</strong>
              <RouterLink
                v-if="dataset?.source_task_id"
                class="secondary-button link-button"
                :to="{ name: 'task-detail', params: { taskId: dataset.source_task_id } }"
              >
                {{ t('datasetDetail.openTask') }}
              </RouterLink>
            </div>
            <div class="trace-card">
              <span>{{ t('datasetDetail.sourceRun') }}</span>
              <strong>{{ sourceRun?.id || signal.task_run_id || dataset?.source_run_id || '-' }}</strong>
              <p v-if="sourceRun">{{ t('tasks.status') }}: {{ labelValue(sourceRun.status) }}</p>
            </div>
            <div class="trace-card">
              <span>{{ t('signalDetail.sourceRow') }}</span>
              <strong>{{ rowIndex ?? '-' }}</strong>
              <p>{{ sourceRef.raw_ref || sourceRef.source_entity_id || '-' }}</p>
            </div>
          </div>
        </BaseSection>

        <BaseSection :title="t('signalDetail.linkedCasesTitle')" :description="t('signalDetail.linkedCasesDescription')">
          <div class="item-list">
            <article v-for="item in linkedCases" :key="item.id" class="list-item">
              <div class="item-main">
                <div>
                  <strong>{{ item.case_name }}</strong>
                  <p>{{ scenarioLabel(item.case_type) }} · {{ item.owner || '-' }}</p>
                </div>
                <StatusBadge :label="labelValue(item.status)" :tone="statusTone(item.status)" />
              </div>
              <p>{{ item.summary || t('cases.noSummary') }}</p>
            </article>
            <EmptyState v-if="!linkedCases.length" :title="t('signalDetail.noLinkedCasesTitle')" :description="t('signalDetail.noLinkedCasesDescription')" />
          </div>
        </BaseSection>
      </div>

      <div class="split-grid">
        <BaseSection :title="t('signalDetail.evidenceFieldsTitle')" :description="t('signalDetail.evidenceFieldsDescription')">
          <template v-if="canReveal" #actions>
            <button
              v-if="!revealed"
              class="secondary-button"
              type="button"
              :disabled="isLoading"
              @click="revealPlaintext"
            >
              {{ t('signalDetail.revealPlaintext') }}
            </button>
            <span v-else class="reveal-note">{{ t('signalDetail.revealed') }}</span>
          </template>
          <div class="field-list">
            <div v-for="field in evidenceFields" :key="field.key" class="field-card">
              <span>{{ field.key }}</span>
              <pre>{{ field.value }}</pre>
            </div>
            <EmptyState v-if="!evidenceFields.length" :title="t('signalDetail.noExtraFields')" />
          </div>
        </BaseSection>

        <BaseSection :title="t('signalDetail.sourceRowPreviewTitle')" :description="t('signalDetail.sourceRowPreviewDescription')">
          <div v-if="selectedPreviewRow" class="preview-wrap">
            <table>
              <thead>
                <tr>
                  <th v-for="column in preview?.columns || []" :key="column">{{ column }}</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td v-for="(cell, index) in selectedPreviewRow" :key="index">{{ cell }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <pre v-else>{{ JSON.stringify(signal.payload_json, null, 2) }}</pre>
        </BaseSection>
      </div>
    </template>
  </section>
</template>

<style scoped>
.reveal-note {
  font-size: 12px;
  font-weight: 800;
  color: var(--warning);
}

.page-grid,
.item-list,
.field-list,
.trace-grid {
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

.hero-panel h1 {
  margin: 6px 0;
  font-size: 30px;
  letter-spacing: 0;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.eyebrow,
.section-head p,
.muted,
.trace-card span,
.trace-card p,
.item-main p,
.list-item p,
.field-card span,
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

.stat-card strong {
  display: block;
  margin-top: 6px;
  font-size: 28px;
  overflow-wrap: anywhere;
}

.section-head {
  margin-bottom: 16px;
}

.section-head h2 {
  margin: 0 0 6px;
}

.trace-card,
.list-item,
.field-card {
  display: grid;
  gap: 8px;
  padding: 14px;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(248, 250, 252, 0.82);
}

.trace-card strong,
.item-main strong {
  overflow-wrap: anywhere;
}

.item-main {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.item-main p,
.list-item p,
.trace-card p {
  margin: 0;
}

.risk-badge,
.status-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.risk-badge.low {
  background: rgba(22, 163, 74, 0.1);
  color: #15803d;
}

.risk-badge.medium {
  background: rgba(217, 119, 6, 0.12);
  color: #b45309;
}

.risk-badge.high,
.risk-badge.critical {
  background: rgba(239, 68, 68, 0.12);
  color: #b91c1c;
}

.status-badge {
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
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

.back-button,
.link-button {
  justify-self: start;
}

.link-button {
  text-decoration: none;
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

.preview-wrap {
  overflow: auto;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.9);
}

table {
  width: 100%;
  min-width: 720px;
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
    display: grid;
    grid-template-columns: 1fr;
  }

  .hero-actions {
    justify-content: start;
  }
}
</style>
