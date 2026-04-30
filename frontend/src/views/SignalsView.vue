<script setup lang="ts">
import { computed, ref } from 'vue'
import { createSignal, deleteSignal, extractSignals, updateSignalStatus } from '../api/signals'
import { useDatasets } from '../composables/useDatasets'
import { useSignals } from '../composables/useSignals'

const {
  items: signalItems,
  isLoading: signalsLoading,
  error: signalsError,
  fetchItems: fetchSignals,
} = useSignals()
const { items: datasetItems } = useDatasets()

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
const selectedSignalId = ref('')
const message = ref('')
const error = ref('')
const busy = ref(false)

const selectedSignal = computed(() =>
  signalItems.value.find((item) => item.id === selectedSignalId.value),
)

const signalStats = computed(() => {
  const stats = [
    { label: 'New', value: signalItems.value.filter((item) => item.status === 'new').length },
    { label: 'Reviewing', value: signalItems.value.filter((item) => item.status === 'reviewing').length },
    { label: 'Confirmed', value: signalItems.value.filter((item) => item.status === 'confirmed').length },
    { label: 'High+', value: signalItems.value.filter((item) => ['high', 'critical'].includes(item.risk_level)).length },
  ]
  return stats
})

function parseList(text: string) {
  return text
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function sourceRef(signal: { payload_json: Record<string, unknown> }) {
  const ref = signal.payload_json.source_ref
  return ref && typeof ref === 'object' ? (ref as Record<string, unknown>) : {}
}

async function submitExtraction() {
  busy.value = true
  message.value = ''
  error.value = ''
  try {
    const signals = await extractSignals({
      dataset_id: extractionForm.value.dataset_id,
      extractors: parseList(extractionForm.value.extractors),
      limit: extractionForm.value.limit,
    })
    message.value = `Extracted ${signals.length} signals.`
    await fetchSignals()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function submitManualSignal() {
  busy.value = true
  message.value = ''
  error.value = ''
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
    message.value = 'Signal created.'
    manualForm.value.summary = ''
    await fetchSignals()
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
    message.value = `Signal marked as ${status}.`
    await fetchSignals()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function removeSignal(signalId: string) {
  message.value = ''
  error.value = ''
  try {
    await deleteSignal(signalId)
    message.value = 'Signal deleted.'
    if (selectedSignalId.value === signalId) selectedSignalId.value = ''
    await fetchSignals()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
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

    <div class="split-grid">
      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Extract From Dataset</h2>
            <p>从数据集预览行中执行规则提取，并保留 dataset、row 和原始引用。</p>
          </div>
        </div>

        <form class="signal-form" @submit.prevent="submitExtraction">
          <label class="field">
            <span>Dataset</span>
            <select v-model="extractionForm.dataset_id" required>
              <option value="" disabled>选择一个数据集</option>
              <option v-for="item in datasetItems" :key="item.id" :value="item.id">
                {{ item.dataset_name }} · {{ item.source_platform }} · {{ item.scenario_type || '-' }}
              </option>
            </select>
          </label>

          <div class="grid-two">
            <label class="field">
              <span>Extractors</span>
              <input
                v-model="extractionForm.extractors"
                placeholder="risk_terms,contact_points,template_similarity,xhs_comment_lead_diversion"
              />
            </label>
            <label class="field">
              <span>Limit</span>
              <input v-model.number="extractionForm.limit" min="1" max="200" step="1" type="number" />
            </label>
          </div>

          <div class="actions">
            <button class="primary-button" :disabled="busy" type="submit">
              {{ busy ? 'Working...' : 'Extract Signals' }}
            </button>
          </div>
        </form>
      </section>

      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Create Manual Signal</h2>
            <p>支持分析师把人工发现的风险线索纳入同一条复核流。</p>
          </div>
        </div>

        <form class="signal-form" @submit.prevent="submitManualSignal">
          <label class="field">
            <span>Dataset</span>
            <select v-model="manualForm.dataset_id" required>
              <option value="" disabled>选择一个数据集</option>
              <option v-for="item in datasetItems" :key="item.id" :value="item.id">
                {{ item.dataset_name }} · {{ item.source_platform }}
              </option>
            </select>
          </label>

          <div class="grid-two">
            <label class="field">
              <span>Risk Level</span>
              <select v-model="manualForm.risk_level">
                <option value="low">low</option>
                <option value="medium">medium</option>
                <option value="high">high</option>
                <option value="critical">critical</option>
              </select>
            </label>
            <label class="field">
              <span>Risk Score</span>
              <input v-model.number="manualForm.risk_score" min="0" max="100" step="1" type="number" />
            </label>
          </div>

          <label class="field">
            <span>Summary</span>
            <textarea v-model="manualForm.summary" required rows="3" placeholder="说明风险依据和可追溯来源" />
          </label>

          <div class="actions">
            <button class="secondary-button" :disabled="busy" type="submit">Create Manual Signal</button>
          </div>
        </form>
      </section>
    </div>

    <div v-if="message" class="success-text">{{ message }}</div>
    <div v-if="error" class="error-text">{{ error }}</div>

    <div class="split-grid">
      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Signal Queue</h2>
            <p>优先处理 high / critical 风险等级和 new 状态。</p>
          </div>
        </div>

        <div v-if="signalsLoading" class="muted">Loading signals...</div>
        <div v-else-if="signalsError" class="error-text">{{ signalsError }}</div>
        <div v-else class="signal-list">
          <article v-for="item in signalItems" :key="item.id" class="signal-item">
            <div class="signal-main">
              <div>
                <strong>{{ item.summary }}</strong>
                <p>{{ item.signal_type }} · {{ item.signal_source }} · score {{ item.risk_score }}</p>
              </div>
              <div class="badge-stack">
                <span class="risk-badge" :class="item.risk_level">{{ item.risk_level }}</span>
                <span class="status-badge">{{ item.status }}</span>
              </div>
            </div>
            <div class="signal-meta">
              <span>{{ item.dataset_id }}</span>
              <span>row {{ sourceRef(item).row_index ?? '-' }}</span>
            </div>
            <div class="actions">
              <button class="secondary-button" type="button" @click="selectedSignalId = item.id">Inspect</button>
              <button class="secondary-button" type="button" @click="setStatus(item.id, 'reviewing')">Review</button>
              <button class="secondary-button" type="button" @click="setStatus(item.id, 'confirmed')">Confirm</button>
              <button class="secondary-button" type="button" @click="setStatus(item.id, 'dismissed')">Dismiss</button>
              <button class="secondary-button destructive" type="button" @click="removeSignal(item.id)">Delete</button>
            </div>
          </article>
          <div v-if="!signalItems.length" class="muted">No signals yet.</div>
        </div>
      </section>

      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Traceability</h2>
            <p>{{ selectedSignal ? selectedSignal.id : '选择一个信号查看来源引用。' }}</p>
          </div>
        </div>

        <div v-if="selectedSignal" class="trace-card">
          <div class="trace-row">
            <span>Dataset</span>
            <strong>{{ selectedSignal.dataset_id }}</strong>
          </div>
          <div class="trace-row">
            <span>Row</span>
            <strong>{{ sourceRef(selectedSignal).row_index ?? '-' }}</strong>
          </div>
          <div class="trace-row">
            <span>Source Entity</span>
            <strong>{{ sourceRef(selectedSignal).source_entity_id || '-' }}</strong>
          </div>
          <div class="trace-row">
            <span>Raw Ref</span>
            <strong>{{ sourceRef(selectedSignal).raw_ref || '-' }}</strong>
          </div>
          <pre>{{ JSON.stringify(selectedSignal.payload_json, null, 2) }}</pre>
        </div>
        <div v-else class="muted">No signal selected.</div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.page-grid,
.signal-form,
.signal-list {
  display: grid;
  gap: 18px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
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

  .split-grid,
  .grid-two,
  .trace-row {
    grid-template-columns: 1fr;
  }
}
</style>
