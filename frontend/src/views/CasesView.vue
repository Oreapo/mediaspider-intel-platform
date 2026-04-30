<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  addCaseLink,
  addCaseNote,
  createCase,
  deleteCase,
  deleteCaseLink,
  deleteCaseNote,
  getCaseDetail,
  updateCase,
} from '../api/cases'
import { useAnalysisJobs } from '../composables/useAnalysisJobs'
import { useCases } from '../composables/useCases'
import { useDatasets } from '../composables/useDatasets'
import { useEntities } from '../composables/useEntities'
import { useSignals } from '../composables/useSignals'
import { getAnalysisOutputs } from '../api/analysis'
import type { AnalysisOutput, CaseDetail } from '../types'

const {
  items: caseItems,
  isLoading: casesLoading,
  error: casesError,
  fetchItems: fetchCases,
} = useCases()
const { items: datasetItems } = useDatasets()
const { items: signalItems } = useSignals()
const { items: entityItems } = useEntities()
const { items: analysisJobItems } = useAnalysisJobs()

const analysisOutputs = ref<AnalysisOutput[]>([])
const selectedDetail = ref<CaseDetail | null>(null)
const busy = ref(false)
const message = ref('')
const error = ref('')

const caseForm = ref({
  case_name: '',
  case_type: 'lead_diversion',
  priority: 'medium',
  owner: '',
  summary: '',
})
const linkForm = ref({
  case_id: '',
  link_type: 'signal',
  target_id: '',
  label: '',
  reason: '',
})
const noteForm = ref({
  case_id: '',
  author: '',
  body: '',
})

const caseStats = computed(() => [
  { label: 'Open', value: caseItems.value.filter((item) => item.status === 'open').length },
  { label: 'Investigating', value: caseItems.value.filter((item) => item.status === 'investigating').length },
  { label: 'High+', value: caseItems.value.filter((item) => ['high', 'critical'].includes(item.priority)).length },
  { label: 'Total', value: caseItems.value.length },
])

const linkTargets = computed(() => {
  if (linkForm.value.link_type === 'dataset') {
    return datasetItems.value.map((item) => ({ id: item.id, label: `${item.dataset_name} · ${item.source_platform}` }))
  }
  if (linkForm.value.link_type === 'signal') {
    return signalItems.value.map((item) => ({ id: item.id, label: `${item.summary} · ${item.status}` }))
  }
  if (linkForm.value.link_type === 'entity') {
    return entityItems.value.map((item) => ({ id: item.id, label: `${item.display_name} · ${item.entity_type}` }))
  }
  if (linkForm.value.link_type === 'analysis_output') {
    return analysisOutputs.value.map((item) => ({ id: item.id, label: `${item.title} · ${item.output_type}` }))
  }
  return []
})

async function loadAnalysisOutputs() {
  const outputs: AnalysisOutput[] = []
  for (const job of analysisJobItems.value) {
    try {
      outputs.push(...(await getAnalysisOutputs(job.id)))
    } catch {
      continue
    }
  }
  analysisOutputs.value = outputs
}

async function submitCase() {
  busy.value = true
  message.value = ''
  error.value = ''
  try {
    const created = await createCase({
      case_name: caseForm.value.case_name,
      case_type: caseForm.value.case_type,
      priority: caseForm.value.priority,
      owner: caseForm.value.owner,
      summary: caseForm.value.summary,
    })
    message.value = 'Case created.'
    caseForm.value.case_name = ''
    caseForm.value.summary = ''
    await fetchCases()
    await inspectCase(created.id)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function submitLink() {
  busy.value = true
  message.value = ''
  error.value = ''
  try {
    await addCaseLink(linkForm.value.case_id, {
      link_type: linkForm.value.link_type,
      target_id: linkForm.value.target_id,
      label: linkForm.value.label,
      source_ref_json: linkForm.value.reason ? { reason: linkForm.value.reason } : {},
    })
    message.value = 'Object attached.'
    linkForm.value.label = ''
    linkForm.value.reason = ''
    await fetchCases()
    await inspectCase(linkForm.value.case_id)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function submitNote() {
  busy.value = true
  message.value = ''
  error.value = ''
  try {
    await addCaseNote(noteForm.value.case_id, {
      author: noteForm.value.author,
      body: noteForm.value.body,
      note_type: 'investigation',
    })
    message.value = 'Note added.'
    noteForm.value.body = ''
    await fetchCases()
    await inspectCase(noteForm.value.case_id)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function inspectCase(caseId: string) {
  message.value = ''
  error.value = ''
  try {
    selectedDetail.value = await getCaseDetail(caseId)
    linkForm.value.case_id = caseId
    noteForm.value.case_id = caseId
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function setCaseStatus(caseId: string, status: string) {
  message.value = ''
  error.value = ''
  try {
    await updateCase(caseId, { status })
    message.value = `Case marked as ${status}.`
    await fetchCases()
    if (selectedDetail.value?.case.id === caseId) await inspectCase(caseId)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function removeCase(caseId: string) {
  message.value = ''
  error.value = ''
  try {
    await deleteCase(caseId)
    message.value = 'Case deleted.'
    if (selectedDetail.value?.case.id === caseId) selectedDetail.value = null
    await fetchCases()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function removeLink(linkId: string) {
  if (!selectedDetail.value) return
  const caseId = selectedDetail.value.case.id
  message.value = ''
  error.value = ''
  try {
    await deleteCaseLink(linkId)
    message.value = 'Link removed.'
    await inspectCase(caseId)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function removeNote(noteId: string) {
  if (!selectedDetail.value) return
  const caseId = selectedDetail.value.case.id
  message.value = ''
  error.value = ''
  try {
    await deleteCaseNote(noteId)
    message.value = 'Note removed.'
    await inspectCase(caseId)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

watch(analysisJobItems, loadAnalysisOutputs, { immediate: true })
</script>

<template>
  <section class="page-grid">
    <div class="stats-grid">
      <article v-for="stat in caseStats" :key="stat.label" class="surface stat-card">
        <span>{{ stat.label }}</span>
        <strong>{{ stat.value }}</strong>
      </article>
    </div>

    <div class="split-grid">
      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Create Case</h2>
            <p>案件是调查容器，用来持续归档线索、实体、分析输出和研判备注。</p>
          </div>
        </div>

        <form class="case-form" @submit.prevent="submitCase">
          <label class="field">
            <span>Case Name</span>
            <input v-model="caseForm.case_name" required placeholder="例：小红书导流链路专项" />
          </label>

          <div class="grid-two">
            <label class="field">
              <span>Case Type</span>
              <select v-model="caseForm.case_type">
                <option value="lead_diversion">lead_diversion</option>
                <option value="gray_recruitment">gray_recruitment</option>
                <option value="fraud_promotion">fraud_promotion</option>
                <option value="seller_risk">seller_risk</option>
                <option value="product_risk">product_risk</option>
                <option value="topic_watch">topic_watch</option>
              </select>
            </label>
            <label class="field">
              <span>Priority</span>
              <select v-model="caseForm.priority">
                <option value="low">low</option>
                <option value="medium">medium</option>
                <option value="high">high</option>
                <option value="critical">critical</option>
              </select>
            </label>
          </div>

          <label class="field">
            <span>Owner</span>
            <input v-model="caseForm.owner" placeholder="analyst" />
          </label>

          <label class="field">
            <span>Summary</span>
            <textarea v-model="caseForm.summary" rows="3" placeholder="案件背景、初始线索和研判目标" />
          </label>

          <div class="actions">
            <button class="primary-button" :disabled="busy" type="submit">
              {{ busy ? 'Working...' : 'Create Case' }}
            </button>
          </div>
        </form>
      </section>

      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Attach Object</h2>
            <p>把已有数据集、信号、实体或分析输出挂到案件。</p>
          </div>
        </div>

        <form class="case-form" @submit.prevent="submitLink">
          <label class="field">
            <span>Case</span>
            <select v-model="linkForm.case_id" required>
              <option value="" disabled>选择案件</option>
              <option v-for="item in caseItems" :key="item.id" :value="item.id">
                {{ item.case_name }} · {{ item.status }}
              </option>
            </select>
          </label>

          <div class="grid-two">
            <label class="field">
              <span>Object Type</span>
              <select v-model="linkForm.link_type" @change="linkForm.target_id = ''">
                <option value="dataset">dataset</option>
                <option value="signal">signal</option>
                <option value="entity">entity</option>
                <option value="analysis_output">analysis_output</option>
              </select>
            </label>
            <label class="field">
              <span>Target</span>
              <select v-model="linkForm.target_id" required>
                <option value="" disabled>选择对象</option>
                <option v-for="item in linkTargets" :key="item.id" :value="item.id">
                  {{ item.label }}
                </option>
              </select>
            </label>
          </div>

          <div class="grid-two">
            <label class="field">
              <span>Label</span>
              <input v-model="linkForm.label" placeholder="可选：关键联系方式 / 首批数据" />
            </label>
            <label class="field">
              <span>Reason</span>
              <input v-model="linkForm.reason" placeholder="挂接原因或证据说明" />
            </label>
          </div>

          <div class="actions">
            <button class="secondary-button" :disabled="busy" type="submit">Attach</button>
          </div>
        </form>
      </section>
    </div>

    <div class="split-grid">
      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Add Note</h2>
            <p>记录调查过程中的判断、疑问和下一步动作。</p>
          </div>
        </div>

        <form class="case-form" @submit.prevent="submitNote">
          <div class="grid-two">
            <label class="field">
              <span>Case</span>
              <select v-model="noteForm.case_id" required>
                <option value="" disabled>选择案件</option>
                <option v-for="item in caseItems" :key="item.id" :value="item.id">
                  {{ item.case_name }}
                </option>
              </select>
            </label>
            <label class="field">
              <span>Author</span>
              <input v-model="noteForm.author" placeholder="analyst" />
            </label>
          </div>

          <label class="field">
            <span>Note</span>
            <textarea v-model="noteForm.body" required rows="4" placeholder="记录研判备注" />
          </label>

          <div class="actions">
            <button class="secondary-button" :disabled="busy" type="submit">Add Note</button>
          </div>
        </form>
      </section>

      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Case Registry</h2>
            <p>案件列表优先展示状态、优先级和负责人。</p>
          </div>
        </div>

        <div v-if="casesLoading" class="muted">Loading cases...</div>
        <div v-else-if="casesError" class="error-text">{{ casesError }}</div>
        <div v-else class="case-list">
          <article v-for="item in caseItems" :key="item.id" class="case-item">
            <div class="case-main">
              <div>
                <strong>{{ item.case_name }}</strong>
                <p>{{ item.case_type }} · {{ item.owner || '-' }}</p>
              </div>
              <div class="badge-stack">
                <span class="priority-badge" :class="item.priority">{{ item.priority }}</span>
                <span class="status-badge">{{ item.status }}</span>
              </div>
            </div>
            <div class="case-summary">{{ item.summary || 'No summary' }}</div>
            <div class="actions">
              <button class="secondary-button" type="button" @click="inspectCase(item.id)">Inspect</button>
              <button class="secondary-button" type="button" @click="setCaseStatus(item.id, 'investigating')">
                Investigate
              </button>
              <button class="secondary-button" type="button" @click="setCaseStatus(item.id, 'ready_for_evidence')">
                Ready
              </button>
              <button class="secondary-button" type="button" @click="setCaseStatus(item.id, 'closed')">Close</button>
              <button class="secondary-button destructive" type="button" @click="removeCase(item.id)">Delete</button>
            </div>
          </article>
          <div v-if="!caseItems.length" class="muted">No cases yet.</div>
        </div>
      </section>
    </div>

    <div v-if="message" class="success-text">{{ message }}</div>
    <div v-if="error" class="error-text">{{ error }}</div>

    <section class="surface section-card">
      <div class="section-head">
        <div>
          <h2>Case Detail</h2>
          <p>{{ selectedDetail ? selectedDetail.case.id : '选择一个案件查看附件、备注和时间线。' }}</p>
        </div>
      </div>

      <div v-if="selectedDetail" class="detail-grid">
        <section class="detail-card">
          <h3>{{ selectedDetail.case.case_name }}</h3>
          <p>{{ selectedDetail.case.summary || 'No summary' }}</p>
          <div class="mini-grid">
            <span>{{ selectedDetail.links.length }} links</span>
            <span>{{ selectedDetail.notes.length }} notes</span>
            <span>{{ selectedDetail.timeline.length }} timeline events</span>
          </div>
        </section>

        <section class="detail-section">
          <h3>Linked Objects</h3>
          <article v-for="item in selectedDetail.links" :key="item.id" class="compact-item">
            <div>
              <strong>{{ item.label || item.target_id }}</strong>
              <span>{{ item.link_type }} · {{ item.target_id }}</span>
            </div>
            <button class="text-button" type="button" @click="removeLink(item.id)">Remove</button>
          </article>
          <div v-if="!selectedDetail.links.length" class="muted">No linked objects.</div>
        </section>

        <section class="detail-section">
          <h3>Notes</h3>
          <article v-for="item in selectedDetail.notes" :key="item.id" class="compact-item">
            <div>
              <strong>{{ item.author || 'unknown' }} · {{ item.note_type }}</strong>
              <span>{{ item.body }}</span>
            </div>
            <button class="text-button" type="button" @click="removeNote(item.id)">Remove</button>
          </article>
          <div v-if="!selectedDetail.notes.length" class="muted">No notes.</div>
        </section>

        <section class="detail-section timeline-section">
          <h3>Timeline</h3>
          <article v-for="item in selectedDetail.timeline" :key="`${item.event_type}-${item.target_id}-${item.event_time}`" class="timeline-item">
            <span>{{ item.event_time }}</span>
            <strong>{{ item.title }}</strong>
            <p>{{ item.event_type }} · {{ item.target_type }}</p>
          </article>
        </section>
      </div>
      <div v-else class="muted">No case selected.</div>
    </section>
  </section>
</template>

<style scoped>
.page-grid,
.case-form,
.case-list,
.detail-section,
.timeline-section {
  display: grid;
  gap: 18px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.split-grid,
.detail-grid {
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
.case-main p,
.case-summary,
.compact-item span,
.detail-card p,
.timeline-item span,
.timeline-item p {
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

.section-head h2,
.detail-section h3,
.detail-card h3 {
  margin: 0 0 6px;
}

.grid-two,
.mini-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.mini-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-top: 14px;
}

.mini-grid span {
  border-radius: 12px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.86);
  font-weight: 700;
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

.case-item,
.compact-item,
.detail-card,
.timeline-item {
  padding: 16px;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(248, 250, 252, 0.82);
}

.case-main,
.compact-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.case-main strong,
.compact-item strong,
.timeline-item strong {
  display: block;
  margin-bottom: 4px;
}

.case-main p,
.timeline-item p,
.detail-card p {
  margin: 0;
}

.case-summary {
  margin: 12px 0;
  font-size: 13px;
}

.badge-stack {
  display: grid;
  justify-items: end;
  gap: 6px;
}

.priority-badge,
.status-badge {
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.priority-badge {
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
}

.priority-badge.high,
.priority-badge.critical {
  background: rgba(239, 68, 68, 0.12);
  color: #b91c1c;
}

.status-badge {
  background: rgba(22, 163, 74, 0.1);
  color: #15803d;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.primary-button,
.secondary-button,
.text-button {
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

.text-button {
  background: transparent;
  color: #b91c1c;
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
  .detail-grid,
  .grid-two,
  .mini-grid {
    grid-template-columns: 1fr;
  }
}
</style>
