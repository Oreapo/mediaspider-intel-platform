<script setup lang="ts">
import { computed, ref } from 'vue'
import { createSignal, deleteSignal, extractSignals, listSignalClusters, updateSignalStatus, type SignalCluster } from '../api/signals'
import AppAlert from '../components/ui/AppAlert.vue'
import AppSelect from '../components/ui/AppSelect.vue'
import BaseSection from '../components/ui/BaseSection.vue'
import EmptyState from '../components/ui/EmptyState.vue'
import FieldError from '../components/ui/FieldError.vue'
import LoadingState from '../components/ui/LoadingState.vue'
import PaginationBar from '../components/ui/PaginationBar.vue'
import PermissionGate from '../components/ui/PermissionGate.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import { useDatasets } from '../composables/useDatasets'
import { useI18n } from '../composables/useI18n'
import { parseList } from '../lib/list'
import { enumLabel as labelValue, scenarioLabel as datasetScenarioLabel } from '../composables/useEnumLabel'
import { useSignals } from '../composables/useSignals'
import { requestConfirm } from '../lib/confirm'
import { lastPageOffset } from '../lib/pagination'
import { nonNegativeNumber, required, type ValidationErrors } from '../lib/validation'

const {
  items: signalItems,
  total: signalTotal,
  isLoading: signalsLoading,
  error: signalsError,
  fetchItems: fetchSignals,
} = useSignals()
const { items: datasetItems } = useDatasets()
const { t } = useI18n()

const extractionForm = ref({
  dataset_id: '',
  extractors:
    'risk_terms,contact_points,template_similarity,abnormal_activity,xhs_comment_lead_diversion,dy_script_diversion,wb_topic_propagation,seller_template_reuse,abnormal_price_band',
  limit: 100,
})
const manualForm = ref({
  dataset_id: '',
  signal_type: 'manual',
  risk_level: 'medium',
  risk_score: 50,
  summary: '',
})
const filters = ref({
  q: '',
  dataset_id: '',
  status: '',
  risk_level: '',
  signal_type: '',
  limit: 100,
  offset: 0,
})
const selectedSignalId = ref('')
const clusters = ref<SignalCluster[]>([])
const message = ref('')
const error = ref('')
const busy = ref(false)
const extractionErrors = ref<ValidationErrors>({})
const manualErrors = ref<ValidationErrors>({})

const selectedSignal = computed(() =>
  signalItems.value.find((item) => item.id === selectedSignalId.value),
)

const signalStats = computed(() => {
  const stats = [
    { label: t('enum.new'), value: signalItems.value.filter((item) => item.status === 'new').length },
    { label: t('enum.reviewing'), value: signalItems.value.filter((item) => item.status === 'reviewing').length },
    { label: t('enum.confirmed'), value: signalItems.value.filter((item) => item.status === 'confirmed').length },
    { label: t('signals.highRiskPlus'), value: signalItems.value.filter((item) => ['high', 'critical'].includes(item.risk_level)).length },
  ]
  return stats
})

const signalTypes = computed(() =>
  Array.from(new Set(signalItems.value.map((item) => item.signal_type))).sort(),
)

function sourceRef(signal: { payload_json: Record<string, unknown> }) {
  const ref = signal.payload_json.source_ref
  return ref && typeof ref === 'object' ? (ref as Record<string, unknown>) : {}
}

function validateExtractionForm() {
  const errors: ValidationErrors = {}
  const datasetError = required(extractionForm.value.dataset_id, t('signals.dataset'))
  const limitError = nonNegativeNumber(extractionForm.value.limit - 1, t('signals.limit'))

  if (datasetError) errors.dataset_id = datasetError
  if (!parseList(extractionForm.value.extractors).length) errors.extractors = t('signals.extractorRequired')
  if (limitError) errors.limit = t('signals.limitInvalid')

  extractionErrors.value = errors
  return Object.keys(errors).length === 0
}

function validateManualForm() {
  const errors: ValidationErrors = {}
  const datasetError = required(manualForm.value.dataset_id, t('signals.dataset'))
  const summaryError = required(manualForm.value.summary, t('signals.summary'))
  const scoreValid = Number.isFinite(manualForm.value.risk_score)
    && manualForm.value.risk_score >= 0
    && manualForm.value.risk_score <= 100

  if (datasetError) errors.dataset_id = datasetError
  if (summaryError) errors.summary = summaryError
  if (!scoreValid) errors.risk_score = t('signals.scoreInvalid')

  manualErrors.value = errors
  return Object.keys(errors).length === 0
}

async function applyFilters() {
  selectedSignalId.value = ''
  filters.value.offset = 0
  await fetchSignalPage()
  await loadClusters()
}

// Candidate gangs (团伙) grouped by shared contact point for the filtered dataset.
async function loadClusters() {
  if (!filters.value.dataset_id) {
    clusters.value = []
    return
  }
  try {
    clusters.value = await listSignalClusters(filters.value.dataset_id)
  } catch {
    clusters.value = []
  }
}

async function fetchSignalPage() {
  await fetchSignals({
    q: filters.value.q,
    dataset_id: filters.value.dataset_id,
    status: filters.value.status,
    risk_level: filters.value.risk_level,
    signal_type: filters.value.signal_type,
    limit: filters.value.limit,
    offset: filters.value.offset,
  })
  const normalizedOffset = lastPageOffset(signalTotal.value, filters.value.limit)
  if (filters.value.offset > normalizedOffset) {
    filters.value.offset = normalizedOffset
    if (signalTotal.value > 0) await fetchSignalPage()
  }
}

async function changeSignalPage(offset: number) {
  selectedSignalId.value = ''
  filters.value.offset = offset
  await fetchSignalPage()
}

async function clearFilters() {
  filters.value = {
    q: '',
    dataset_id: '',
    status: '',
    risk_level: '',
    signal_type: '',
    limit: 100,
    offset: 0,
  }
  await applyFilters()
}

async function submitExtraction() {
  message.value = ''
  error.value = ''
  if (!validateExtractionForm()) {
    error.value = t('signals.fixExtractionErrors')
    return
  }

  busy.value = true
  try {
    const result = await extractSignals({
      dataset_id: extractionForm.value.dataset_id,
      extractors: parseList(extractionForm.value.extractors),
      limit: extractionForm.value.limit,
    })
    message.value = result.created_count > 0
      ? t('signals.extractedMessage', { count: result.created_count })
      : t('signals.extractDedupedMessage')
    await fetchSignalPage()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function submitManualSignal() {
  message.value = ''
  error.value = ''
  if (!validateManualForm()) {
    error.value = t('signals.fixManualErrors')
    return
  }

  busy.value = true
  try {
    await createSignal({
      dataset_id: manualForm.value.dataset_id,
      signal_type: manualForm.value.signal_type,
      signal_source: 'manual',
      risk_level: manualForm.value.risk_level,
      risk_score: manualForm.value.risk_score,
      summary: manualForm.value.summary,
      payload_json: {
        source_ref: {
          dataset_id: manualForm.value.dataset_id,
          row_index: null,
        },
      },
    })
    message.value = t('signals.createdMessage')
    manualForm.value.summary = ''
    await fetchSignalPage()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function setStatus(signalId: string, status: string) {
  message.value = ''
  error.value = ''
  try {
    await updateSignalStatus(signalId, status)
    message.value = t('signals.statusUpdated', { status: labelValue(status) })
    await fetchSignalPage()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function removeSignal(signalId: string) {
  const confirmed = await requestConfirm({
    title: t('signals.deleteTitle'),
    message: t('signals.deleteMessage'),
    confirmLabel: t('signals.deleteConfirm'),
  })
  if (!confirmed) return

  message.value = ''
  error.value = ''
  try {
    await deleteSignal(signalId)
    message.value = t('signals.deletedMessage')
    if (selectedSignalId.value === signalId) selectedSignalId.value = ''
    await fetchSignalPage()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
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

</script>

<template>
  <section class="page-grid">
    <div class="stats-grid">
      <article v-for="stat in signalStats" :key="stat.label" class="surface stat-card">
        <span>{{ stat.label }}</span>
        <strong>{{ stat.value }}</strong>
      </article>
    </div>

    <div class="signal-workspace">
      <aside class="signal-side-panel">
    <div class="signal-action-stack">
      <BaseSection compact :title="t('signals.extractTitle')" :description="t('signals.extractDescription')">
        <PermissionGate area="analysis">
        <form class="signal-form" @submit.prevent="submitExtraction">
          <label class="field">
            <span>{{ t('signals.dataset') }}</span>
            <AppSelect
              v-model="extractionForm.dataset_id"
              :placeholder="t('signals.chooseDataset')"
              :options="datasetItems.map((item) => ({
                value: item.id,
                label: `${item.dataset_name} · ${item.source_platform} · ${datasetScenarioLabel(item.scenario_type)}`,
              }))"
            />
            <FieldError :message="extractionErrors.dataset_id" />
          </label>

          <div class="grid-two">
            <label class="field">
              <span>{{ t('signals.extractors') }}</span>
              <input
                v-model="extractionForm.extractors"
                placeholder="risk_terms,contact_points,template_similarity,xhs_comment_lead_diversion"
              />
              <FieldError :message="extractionErrors.extractors" />
            </label>
            <label class="field">
              <span>{{ t('signals.limit') }}</span>
              <input v-model.number="extractionForm.limit" min="1" max="200" step="1" type="number" />
              <FieldError :message="extractionErrors.limit" />
            </label>
          </div>

          <div class="actions">
            <button class="primary-button" :disabled="busy" type="submit">
              {{ busy ? t('signals.processing') : t('signals.extract') }}
            </button>
          </div>
        </form>
        </PermissionGate>
      </BaseSection>

      <BaseSection compact :title="t('signals.manualTitle')" :description="t('signals.manualDescription')">
        <PermissionGate area="analysis">
        <form class="signal-form" @submit.prevent="submitManualSignal">
          <label class="field">
            <span>{{ t('signals.dataset') }}</span>
            <AppSelect
              v-model="manualForm.dataset_id"
              :placeholder="t('signals.chooseDataset')"
              :options="datasetItems.map((item) => ({
                value: item.id,
                label: `${item.dataset_name} · ${item.source_platform}`,
              }))"
            />
            <FieldError :message="manualErrors.dataset_id" />
          </label>

          <div class="grid-two">
            <label class="field">
              <span>{{ t('signals.riskLevel') }}</span>
              <AppSelect
                v-model="manualForm.risk_level"
                :options="[
                  { value: 'low', label: t('enum.low') },
                  { value: 'medium', label: t('enum.medium') },
                  { value: 'high', label: t('enum.high') },
                  { value: 'critical', label: t('enum.critical') },
                ]"
              />
            </label>
            <label class="field">
              <span>{{ t('signals.riskScore') }}</span>
              <input v-model.number="manualForm.risk_score" min="0" max="100" step="1" type="number" />
              <FieldError :message="manualErrors.risk_score" />
            </label>
          </div>

          <label class="field">
            <span>{{ t('signals.summary') }}</span>
            <textarea v-model="manualForm.summary" required rows="3" :placeholder="t('signals.summaryPlaceholder')" />
            <FieldError :message="manualErrors.summary" />
          </label>

          <div class="actions">
            <button class="secondary-button" :disabled="busy" type="submit">{{ t('signals.createManual') }}</button>
          </div>
        </form>
        </PermissionGate>
      </BaseSection>
    </div>

    <AppAlert v-if="message" tone="success" :title="t('tasks.successTitle')" :message="message" />
    <AppAlert v-if="error" tone="error" :title="t('tasks.actionFailedTitle')" :message="error" />
      </aside>

      <main class="signal-main-panel">
    <BaseSection :title="t('signals.filterTitle')" :description="t('signals.filterDescription')">
      <form class="filter-form" @submit.prevent="applyFilters">
        <label class="field">
          <span>{{ t('tasks.search') }}</span>
          <input v-model="filters.q" :placeholder="t('signals.searchPlaceholder')" />
        </label>

        <label class="field">
          <span>{{ t('signals.dataset') }}</span>
          <AppSelect
            v-model="filters.dataset_id"
            :options="[
              { value: '', label: t('signals.allDatasets') },
              ...datasetItems.map((item) => ({ value: item.id, label: `${item.dataset_name} · ${item.source_platform}` })),
            ]"
          />
        </label>

        <label class="field">
          <span>{{ t('tasks.status') }}</span>
          <AppSelect
            v-model="filters.status"
            :options="[
              { value: '', label: t('signals.allStatuses') },
              { value: 'new', label: t('enum.new') },
              { value: 'reviewing', label: t('enum.reviewing') },
              { value: 'confirmed', label: t('enum.confirmed') },
              { value: 'dismissed', label: t('enum.dismissed') },
            ]"
          />
        </label>

        <label class="field">
          <span>{{ t('signals.risk') }}</span>
          <AppSelect
            v-model="filters.risk_level"
            :options="[
              { value: '', label: t('signals.allRisks') },
              { value: 'critical', label: t('enum.critical') },
              { value: 'high', label: t('enum.high') },
              { value: 'medium', label: t('enum.medium') },
              { value: 'low', label: t('enum.low') },
            ]"
          />
        </label>

        <label class="field">
          <span>{{ t('signals.type') }}</span>
          <AppSelect
            v-model="filters.signal_type"
            :options="[
              { value: '', label: t('signals.allTypes') },
              ...signalTypes.map((item) => ({ value: item, label: item })),
            ]"
          />
        </label>

        <label class="field">
          <span>{{ t('signals.limit') }}</span>
          <input v-model.number="filters.limit" min="1" max="500" step="1" type="number" />
        </label>

        <div class="actions filter-actions">
          <button class="primary-button" :disabled="signalsLoading" type="submit">{{ t('tasks.apply') }}</button>
          <button class="secondary-button" :disabled="signalsLoading" type="button" @click="clearFilters">{{ t('tasks.clear') }}</button>
        </div>
      </form>
    </BaseSection>

    <BaseSection
      v-if="filters.dataset_id && clusters.length"
      :title="t('signals.clustersTitle')"
      :description="t('signals.clustersDescription')"
    >
      <div class="cluster-grid">
        <article v-for="cluster in clusters" :key="cluster.contact_point" class="cluster-card">
          <div class="cluster-head">
            <strong>{{ cluster.contact_point }}</strong>
            <small>{{ t('signals.clusterSignalCount', { count: cluster.signal_count }) }}</small>
          </div>
          <div class="cluster-risks">
            <span v-for="(count, level) in cluster.risk_levels" :key="level" class="cluster-risk">
              {{ labelValue(String(level)) }} · {{ count }}
            </span>
          </div>
        </article>
      </div>
    </BaseSection>

    <div class="split-grid">
      <BaseSection :title="t('signals.queueTitle')" :description="t('signals.queueDescription')">
        <LoadingState v-if="signalsLoading" :title="t('signals.loading')" />
        <AppAlert v-else-if="signalsError" tone="error" :title="t('common.loadFailed')" :message="signalsError" />
        <div v-else class="signal-list">
          <article v-for="item in signalItems" :key="item.id" class="signal-item">
            <div class="signal-main">
              <div>
                <strong>{{ item.summary }}</strong>
                <p>{{ labelValue(item.signal_type) }} · {{ item.signal_source }} · {{ t('signals.score', { score: item.risk_score }) }}</p>
              </div>
              <div class="badge-stack">
                <StatusBadge :label="labelValue(item.risk_level)" :tone="riskTone(item.risk_level)" />
                <StatusBadge :label="labelValue(item.status)" :tone="statusTone(item.status)" />
              </div>
            </div>
            <div class="signal-meta">
              <span>{{ item.dataset_id }}</span>
              <span>{{ t('signals.row', { row: String(sourceRef(item).row_index ?? '-') }) }}</span>
            </div>
            <div class="actions">
              <RouterLink class="secondary-button link-button" :to="{ name: 'signal-detail', params: { signalId: item.id } }">
                {{ t('signals.viewDetail') }}
              </RouterLink>
              <button class="secondary-button" type="button" @click="selectedSignalId = item.id">{{ t('signals.view') }}</button>
              <PermissionGate area="analysis" compact>
              <button class="secondary-button" type="button" @click="setStatus(item.id, 'reviewing')">{{ t('signals.review') }}</button>
              <button class="secondary-button" type="button" @click="setStatus(item.id, 'confirmed')">{{ t('signals.confirm') }}</button>
              <button class="secondary-button" type="button" @click="setStatus(item.id, 'dismissed')">{{ t('signals.dismiss') }}</button>
              <button class="secondary-button destructive" type="button" @click="removeSignal(item.id)">{{ t('signals.delete') }}</button>
              </PermissionGate>
            </div>
          </article>
          <EmptyState v-if="!signalItems.length" :title="t('signals.emptyTitle')" :description="t('signals.emptyDescription')" />
          <PaginationBar
            :total="signalTotal"
            :limit="filters.limit"
            :offset="filters.offset"
            :loading="signalsLoading"
            @change="changeSignalPage"
          />
        </div>
      </BaseSection>

      <BaseSection :title="t('signals.traceTitle')" :description="selectedSignal ? selectedSignal.id : t('signals.traceDescription')">
        <div v-if="selectedSignal" class="trace-card">
          <div class="trace-row">
            <span>{{ t('signals.dataset') }}</span>
            <strong>{{ selectedSignal.dataset_id }}</strong>
          </div>
          <div class="trace-row">
            <span>{{ t('signals.rowNumber') }}</span>
            <strong>{{ sourceRef(selectedSignal).row_index ?? '-' }}</strong>
          </div>
          <div class="trace-row">
            <span>{{ t('signals.sourceEntity') }}</span>
            <strong>{{ sourceRef(selectedSignal).source_entity_id || '-' }}</strong>
          </div>
          <div class="trace-row">
            <span>{{ t('signals.rawRef') }}</span>
            <strong>{{ sourceRef(selectedSignal).raw_ref || '-' }}</strong>
          </div>
          <pre>{{ JSON.stringify(selectedSignal.payload_json, null, 2) }}</pre>
        </div>
        <EmptyState v-else :title="t('signals.noSelectionTitle')" :description="t('signals.noSelectionDescription')" />
      </BaseSection>
    </div>
      </main>
    </div>
  </section>
</template>

<style scoped>
.page-grid,
.signal-form,
.signal-list,
.filter-form {
  display: grid;
  gap: 18px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.signal-workspace {
  display: grid;
  grid-template-columns: minmax(320px, 380px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.signal-side-panel {
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

.signal-main-panel {
  min-width: 0;
}

.signal-action-stack {
  display: grid;
  gap: 14px;
}

.signal-side-panel .grid-two {
  grid-template-columns: 1fr;
}

.signal-side-panel .actions {
  display: grid;
}

.signal-side-panel .primary-button,
.signal-side-panel .secondary-button {
  width: 100%;
}

.split-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
}

.section-card,
.stat-card {
  border-radius: 24px;
  padding: 22px;
}

.stat-card span,
.section-head p,
.muted,
.field span,
.signal-item p,
.signal-meta,
.trace-row span {
  color: #64748b;
}

.stat-card strong {
  display: block;
  margin-top: 6px;
  font-size: 34px;
}

.section-head {
  margin-bottom: 16px;
}

.section-head h2 {
  margin: 0 0 6px;
}

.grid-two {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
}

.filter-form .field {
  flex: 1 1 158px;
  min-width: 150px;
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
.field select,
.field textarea {
  width: 100%;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid rgba(203, 213, 225, 0.95);
  background: rgba(255, 255, 255, 0.94);
}

.field textarea {
  resize: vertical;
}

.signal-item,
.trace-card {
  padding: 16px;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(248, 250, 252, 0.82);
}

.signal-main {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.signal-main strong {
  display: block;
  margin-bottom: 4px;
}

.signal-main p {
  margin: 0;
}

.badge-stack {
  display: grid;
  justify-items: end;
  gap: 6px;
}

.risk-badge,
.status-badge {
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

.signal-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin: 12px 0;
  font-size: 13px;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.filter-actions {
  flex-wrap: nowrap;
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

.link-button {
  display: inline-flex;
  align-items: center;
  text-decoration: none;
}

.secondary-button.destructive {
  background: rgba(254, 226, 226, 0.95);
  color: #b91c1c;
}

.trace-row {
  display: grid;
  grid-template-columns: 130px minmax(0, 1fr);
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(226, 232, 240, 0.9);
}

.trace-row strong {
  min-width: 0;
  overflow-wrap: anywhere;
}

pre {
  margin: 14px 0 0;
  padding: 14px;
  overflow: auto;
  border-radius: 14px;
  background: #0f172a;
  color: #e2e8f0;
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

  .signal-workspace {
    grid-template-columns: 1fr;
  }

  .signal-side-panel {
    position: static;
    max-height: none;
    overflow: visible;
    padding-right: 0;
  }

  .split-grid,
  .grid-two,
  .trace-row,
  .filter-form {
    grid-template-columns: 1fr;
  }
}

.cluster-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}

.cluster-card {
  display: grid;
  gap: 8px;
  padding: 12px 14px;
  border-radius: var(--radius);
  border: 1px solid rgba(215, 224, 234, 0.86);
  background: rgba(248, 250, 252, 0.84);
}

.cluster-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}

.cluster-head strong {
  min-width: 0;
  overflow-wrap: anywhere;
  font-family: var(--font-mono);
}

.cluster-head small {
  flex-shrink: 0;
  color: #64748b;
  font-weight: 800;
}

.cluster-risks {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.cluster-risk {
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(226, 232, 240, 0.82);
  color: #475569;
  font-size: 12px;
  font-weight: 700;
}
</style>
