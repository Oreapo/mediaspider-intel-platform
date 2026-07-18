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
import AppAlert from '../components/ui/AppAlert.vue'
import AppIcon from '../components/ui/AppIcon.vue'
import AppSelect from '../components/ui/AppSelect.vue'
import BaseSection from '../components/ui/BaseSection.vue'
import EmptyState from '../components/ui/EmptyState.vue'
import FieldError from '../components/ui/FieldError.vue'
import LoadingState from '../components/ui/LoadingState.vue'
import PaginationBar from '../components/ui/PaginationBar.vue'
import PermissionGate from '../components/ui/PermissionGate.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import { useAnalysisJobs } from '../composables/useAnalysisJobs'
import { useCases } from '../composables/useCases'
import { useDatasets } from '../composables/useDatasets'
import { useEntities } from '../composables/useEntities'
import { useI18n } from '../composables/useI18n'
import { enumLabel as labelValue, scenarioLabel } from '../composables/useEnumLabel'
import { useSignals } from '../composables/useSignals'
import { getAnalysisOutputsBatch } from '../api/analysis'
import { downloadEvidencePacket, generateEvidencePacket } from '../api/evidence'
import { requestConfirm } from '../lib/confirm'
import { lastPageOffset } from '../lib/pagination'
import { required, type ValidationErrors } from '../lib/validation'
import type { AnalysisOutput, CaseDetail, CaseTimelineItem } from '../types'

const {
  items: caseItems,
  total: caseTotal,
  isLoading: casesLoading,
  error: casesError,
  fetchItems: fetchCases,
} = useCases()
const { items: datasetItems } = useDatasets()
const { items: signalItems } = useSignals()
const { items: entityItems } = useEntities()
const { items: analysisJobItems } = useAnalysisJobs()
const { t } = useI18n()

const analysisOutputs = ref<AnalysisOutput[]>([])
let analysisOutputsRequestId = 0
const selectedDetail = ref<CaseDetail | null>(null)
const busy = ref(false)
const downloadingEvidenceId = ref('')
const message = ref('')
const error = ref('')
const caseErrors = ref<ValidationErrors>({})
const linkErrors = ref<ValidationErrors>({})
const noteErrors = ref<ValidationErrors>({})

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
const evidenceForm = ref({
  packet_name: '',
})
const filters = ref({
  q: '',
  status: '',
  priority: '',
  case_type: '',
  owner: '',
  limit: 100,
  offset: 0,
})

const caseStats = computed(() => [
  { label: t('cases.open'), value: caseItems.value.filter((item) => item.status === 'open').length, icon: 'briefcase', color: 'var(--primary)' },
  { label: t('cases.investigating'), value: caseItems.value.filter((item) => item.status === 'investigating').length, icon: 'search', color: '#cf8214' },
  { label: t('cases.highPriorityPlus'), value: caseItems.value.filter((item) => ['high', 'critical'].includes(item.priority)).length, icon: 'alert', color: '#dc4536' },
  { label: t('cases.total'), value: caseItems.value.length, icon: 'layers', color: '#64748b' },
])

const caseTypes = computed(() => Array.from(new Set(caseItems.value.map((item) => item.case_type))).sort())

const evidenceTree = computed(() => {
  if (!selectedDetail.value) return []
  const detail = selectedDetail.value
  return [
    {
      key: 'datasets',
      title: t('datasets.listTitle'),
      count: detail.objects.datasets.length,
      items: detail.objects.datasets.map((item) => ({
        id: item.id,
        title: item.dataset_name,
        meta: `${item.source_platform} · ${t('datasets.recordCount', { count: item.record_count })}`,
      })),
    },
    {
      key: 'signals',
      title: t('signals.queueTitle'),
      count: detail.objects.signals.length,
      items: detail.objects.signals.map((item) => ({
        id: item.id,
        title: item.summary,
        meta: `${labelValue(item.risk_level)} · ${labelValue(item.status)}`,
      })),
    },
    {
      key: 'entities',
      title: t('nav.entities'),
      count: detail.objects.entities.length,
      items: detail.objects.entities.map((item) => ({
        id: item.id,
        title: item.display_name,
        meta: `${item.platform} · ${item.entity_type} · ${item.risk_score}`,
      })),
    },
    {
      key: 'analysis',
      title: t('cases.analysisOutputs'),
      count: detail.objects.analysis_outputs.length,
      items: detail.objects.analysis_outputs.map((item) => ({
        id: item.id,
        title: item.title,
        meta: item.output_type,
      })),
    },
    {
      key: 'evidence',
      title: t('cases.evidencePacks'),
      count: detail.objects.evidence_packets.length,
      items: detail.objects.evidence_packets.map((item) => ({
        id: item.id,
        title: item.packet_name,
        meta: item.storage_uri,
      })),
    },
  ]
})

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
  const requestId = ++analysisOutputsRequestId
  try {
    const outputs = await getAnalysisOutputsBatch(analysisJobItems.value.map((job) => job.id))
    if (requestId === analysisOutputsRequestId) {
      analysisOutputs.value = outputs
    }
  } catch {
    if (requestId === analysisOutputsRequestId) {
      analysisOutputs.value = []
    }
  }
}

function validateCaseForm() {
  const errors: ValidationErrors = {}
  const nameError = required(caseForm.value.case_name, t('cases.name'))
  if (nameError) errors.case_name = nameError
  caseErrors.value = errors
  return Object.keys(errors).length === 0
}

function validateLinkForm() {
  const errors: ValidationErrors = {}
  const caseError = required(linkForm.value.case_id, t('cases.case'))
  const targetError = required(linkForm.value.target_id, t('cases.target'))
  if (caseError) errors.case_id = caseError
  if (targetError) errors.target_id = targetError
  linkErrors.value = errors
  return Object.keys(errors).length === 0
}

function validateNoteForm() {
  const errors: ValidationErrors = {}
  const caseError = required(noteForm.value.case_id, t('cases.case'))
  const bodyError = required(noteForm.value.body, t('cases.note'))
  if (caseError) errors.case_id = caseError
  if (bodyError) errors.body = bodyError
  noteErrors.value = errors
  return Object.keys(errors).length === 0
}

async function submitCase() {
  message.value = ''
  error.value = ''
  if (!validateCaseForm()) {
    error.value = t('cases.fixCaseErrors')
    return
  }

  busy.value = true
  try {
    const created = await createCase({
      case_name: caseForm.value.case_name,
      case_type: caseForm.value.case_type,
      priority: caseForm.value.priority,
      owner: caseForm.value.owner,
      summary: caseForm.value.summary,
    })
    message.value = t('cases.createdMessage')
    caseForm.value.case_name = ''
    caseForm.value.summary = ''
    await fetchCasePage()
    await inspectCase(created.id)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function submitLink() {
  message.value = ''
  error.value = ''
  if (!validateLinkForm()) {
    error.value = t('cases.fixLinkErrors')
    return
  }

  busy.value = true
  try {
    await addCaseLink(linkForm.value.case_id, {
      link_type: linkForm.value.link_type,
      target_id: linkForm.value.target_id,
      label: linkForm.value.label,
      source_ref_json: linkForm.value.reason ? { reason: linkForm.value.reason } : {},
    })
    message.value = t('cases.linkedMessage')
    linkForm.value.label = ''
    linkForm.value.reason = ''
    await fetchCasePage()
    await inspectCase(linkForm.value.case_id)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function submitNote() {
  message.value = ''
  error.value = ''
  if (!validateNoteForm()) {
    error.value = t('cases.fixNoteErrors')
    return
  }

  busy.value = true
  try {
    await addCaseNote(noteForm.value.case_id, {
      author: noteForm.value.author,
      body: noteForm.value.body,
      note_type: 'investigation',
    })
    message.value = t('cases.noteAddedMessage')
    noteForm.value.body = ''
    await fetchCasePage()
    await inspectCase(noteForm.value.case_id)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function generatePacketForSelectedCase() {
  if (!selectedDetail.value) return
  const caseId = selectedDetail.value.case.id
  busy.value = true
  message.value = ''
  error.value = ''
  try {
    const packetName =
      evidenceForm.value.packet_name ||
      `${selectedDetail.value.case.case_name} evidence packet ${new Date().toISOString().slice(0, 10)}`
    await generateEvidencePacket({
      case_id: caseId,
      packet_name: packetName,
    })
    evidenceForm.value.packet_name = ''
    message.value = t('cases.packetGeneratedMessage')
    await fetchCasePage()
    await inspectCase(caseId)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function applyFilters() {
  selectedDetail.value = null
  filters.value.offset = 0
  await fetchCasePage()
}

async function fetchCasePage() {
  await fetchCases({
    q: filters.value.q,
    status: filters.value.status,
    priority: filters.value.priority,
    case_type: filters.value.case_type,
    owner: filters.value.owner,
    limit: filters.value.limit,
    offset: filters.value.offset,
  })
  const normalizedOffset = lastPageOffset(caseTotal.value, filters.value.limit)
  if (filters.value.offset > normalizedOffset) {
    filters.value.offset = normalizedOffset
    if (caseTotal.value > 0) await fetchCasePage()
  }
}

async function changeCasePage(offset: number) {
  selectedDetail.value = null
  filters.value.offset = offset
  await fetchCasePage()
}

async function clearFilters() {
  filters.value = {
    q: '',
    status: '',
    priority: '',
    case_type: '',
    owner: '',
    limit: 100,
    offset: 0,
  }
  await applyFilters()
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

async function downloadEvidence(packetId: string) {
  message.value = ''
  error.value = ''
  downloadingEvidenceId.value = packetId
  try {
    await downloadEvidencePacket(packetId)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    downloadingEvidenceId.value = ''
  }
}

async function setCaseStatus(caseId: string, status: string) {
  message.value = ''
  error.value = ''
  try {
    await updateCase(caseId, { status })
    message.value = t('cases.statusUpdated', { status: labelValue(status) })
    await fetchCasePage()
    if (selectedDetail.value?.case.id === caseId) await inspectCase(caseId)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function removeCase(caseId: string) {
  const confirmed = await requestConfirm({
    title: t('cases.deleteTitle'),
    message: t('cases.deleteMessage'),
    confirmLabel: t('cases.deleteConfirm'),
  })
  if (!confirmed) return

  message.value = ''
  error.value = ''
  try {
    await deleteCase(caseId)
    message.value = t('cases.deletedMessage')
    if (selectedDetail.value?.case.id === caseId) selectedDetail.value = null
    await fetchCasePage()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function removeLink(linkId: string) {
  if (!selectedDetail.value) return
  const confirmed = await requestConfirm({
    title: t('cases.removeLinkTitle'),
    message: t('cases.removeLinkMessage'),
    confirmLabel: t('cases.removeLinkConfirm'),
    tone: 'warning',
  })
  if (!confirmed) return

  const caseId = selectedDetail.value.case.id
  message.value = ''
  error.value = ''
  try {
    await deleteCaseLink(linkId)
    message.value = t('cases.linkRemovedMessage')
    await inspectCase(caseId)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function removeNote(noteId: string) {
  if (!selectedDetail.value) return
  const confirmed = await requestConfirm({
    title: t('cases.deleteNoteTitle'),
    message: t('cases.deleteNoteMessage'),
    confirmLabel: t('cases.deleteNoteConfirm'),
  })
  if (!confirmed) return

  const caseId = selectedDetail.value.case.id
  message.value = ''
  error.value = ''
  try {
    await deleteCaseNote(noteId)
    message.value = t('cases.noteRemovedMessage')
    await inspectCase(caseId)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

function priorityTone(priority: string) {
  if (['critical', 'high'].includes(priority)) return 'danger'
  if (priority === 'medium') return 'warning'
  if (priority === 'low') return 'success'
  return 'neutral'
}

function priorityColor(priority: string) {
  const map: Record<string, string> = {
    critical: '#dc2626',
    high: '#ea6a1f',
    medium: '#cf8214',
    low: '#17915a',
  }
  return map[priority] || '#94a3b8'
}

function caseStatusTone(status: string) {
  if (status === 'closed') return 'neutral'
  if (status === 'ready_for_evidence') return 'warning'
  if (status === 'investigating') return 'info'
  if (status === 'open') return 'success'
  return 'neutral'
}

function auditActionLabel(action: string) {
  const key = `auditAction.${action}`
  const translated = t(key)
  return translated === key ? action : translated
}

function timelineTitle(item: CaseTimelineItem) {
  if (item.event_type !== 'case_status_changed') return item.title
  const previousStatus = String(item.source_ref.previous_status || '')
  const newStatus = String(item.source_ref.new_status || '')
  return `${labelValue(previousStatus)} → ${labelValue(newStatus)}`
}

function timelineEventLabel(eventType: string) {
  const key = `cases.timelineEvent.${eventType}`
  const translated = t(key)
  return translated === key ? eventType : translated
}

function formatDate(value: string | null) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

watch(analysisJobItems, loadAnalysisOutputs, { immediate: true })
</script>

<template>
  <section class="page-grid">
    <div class="stats-grid">
      <article
        v-for="stat in caseStats"
        :key="stat.label"
        class="surface stat-card"
        :style="{ '--stat-accent': stat.color }"
      >
        <div class="stat-top">
          <span>{{ stat.label }}</span>
          <span class="stat-icon"><AppIcon :name="stat.icon" :size="18" /></span>
        </div>
        <strong>{{ stat.value }}</strong>
      </article>
    </div>

    <div class="case-workspace">
      <aside class="case-side-panel">
        <div class="case-action-stack">
          <BaseSection compact :title="t('cases.createTitle')" :description="t('cases.createDescription')">
            <PermissionGate area="analysis">
              <form class="case-form" @submit.prevent="submitCase">
                <label class="field">
                  <span>{{ t('cases.name') }}</span>
                  <input v-model="caseForm.case_name" required :placeholder="t('cases.namePlaceholder')" />
                  <FieldError :message="caseErrors.case_name" />
                </label>

                <div class="grid-two">
                  <label class="field">
                    <span>{{ t('cases.type') }}</span>
                    <AppSelect
                      v-model="caseForm.case_type"
                      :options="[
                        { value: 'lead_diversion', label: t('scenario.lead_diversion') },
                        { value: 'gray_recruitment', label: t('scenario.gray_recruitment') },
                        { value: 'fraud_promotion', label: t('scenario.fraud_promotion') },
                        { value: 'seller_risk', label: t('scenario.seller_risk') },
                        { value: 'product_risk', label: t('scenario.product_risk') },
                        { value: 'topic_watch', label: t('scenario.topic_watch') },
                      ]"
                    />
                  </label>
                  <label class="field">
                    <span>{{ t('cases.priority') }}</span>
                    <AppSelect
                      v-model="caseForm.priority"
                      :options="[
                        { value: 'low', label: t('enum.low') },
                        { value: 'medium', label: t('enum.medium') },
                        { value: 'high', label: t('enum.high') },
                        { value: 'critical', label: t('enum.critical') },
                      ]"
                    />
                  </label>
                </div>

                <label class="field">
                  <span>{{ t('cases.owner') }}</span>
                  <input v-model="caseForm.owner" placeholder="analyst" />
                </label>

                <label class="field">
                  <span>{{ t('cases.summary') }}</span>
                  <textarea v-model="caseForm.summary" rows="3" :placeholder="t('cases.summaryPlaceholder')"></textarea>
                </label>

                <div class="actions">
                  <button class="primary-button" :disabled="busy" type="submit">
                    {{ busy ? t('signals.processing') : t('cases.create') }}
                  </button>
                </div>
              </form>
            </PermissionGate>
          </BaseSection>

          <BaseSection compact :title="t('cases.linkTitle')" :description="t('cases.linkDescription')">
            <PermissionGate area="analysis">
              <form class="case-form" @submit.prevent="submitLink">
                <label class="field">
                  <span>{{ t('cases.case') }}</span>
                  <AppSelect
                    v-model="linkForm.case_id"
                    :placeholder="t('cases.chooseCase')"
                    :options="caseItems.map((item) => ({
                      value: item.id,
                      label: `${item.case_name} · ${labelValue(item.status)}`,
                    }))"
                  />
                  <FieldError :message="linkErrors.case_id" />
                </label>

                <div class="grid-two">
                  <label class="field">
                    <span>{{ t('cases.objectType') }}</span>
                    <AppSelect
                      v-model="linkForm.link_type"
                      :options="[
                        { value: 'dataset', label: t('enum.dataset') },
                        { value: 'signal', label: t('enum.signal') },
                        { value: 'entity', label: t('enum.entity') },
                        { value: 'analysis_output', label: t('enum.analysis_output') },
                      ]"
                      @change="linkForm.target_id = ''"
                    />
                  </label>
                  <label class="field">
                    <span>{{ t('cases.target') }}</span>
                    <AppSelect
                      v-model="linkForm.target_id"
                      :placeholder="t('cases.chooseObject')"
                      :options="linkTargets.map((item) => ({ value: item.id, label: item.label }))"
                    />
                    <FieldError :message="linkErrors.target_id" />
                  </label>
                </div>

                <div class="grid-two">
                  <label class="field">
                    <span>{{ t('cases.label') }}</span>
                    <input v-model="linkForm.label" :placeholder="t('cases.labelPlaceholder')" />
                  </label>
                  <label class="field">
                    <span>{{ t('cases.reason') }}</span>
                    <input v-model="linkForm.reason" :placeholder="t('cases.reasonPlaceholder')" />
                  </label>
                </div>

                <div class="actions">
                  <button class="secondary-button" :disabled="busy" type="submit">{{ t('cases.link') }}</button>
                </div>
              </form>
            </PermissionGate>
          </BaseSection>

          <BaseSection compact :title="t('cases.noteTitle')" :description="t('cases.noteDescription')">
            <PermissionGate area="analysis">
              <form class="case-form" @submit.prevent="submitNote">
                <div class="grid-two">
                  <label class="field">
                    <span>{{ t('cases.case') }}</span>
                    <AppSelect
                      v-model="noteForm.case_id"
                      :placeholder="t('cases.chooseCase')"
                      :options="caseItems.map((item) => ({ value: item.id, label: item.case_name }))"
                    />
                    <FieldError :message="noteErrors.case_id" />
                  </label>
                  <label class="field">
                    <span>{{ t('cases.author') }}</span>
                    <input v-model="noteForm.author" placeholder="analyst" />
                  </label>
                </div>

                <label class="field">
                  <span>{{ t('cases.note') }}</span>
                  <textarea v-model="noteForm.body" required rows="4" :placeholder="t('cases.notePlaceholder')"></textarea>
                  <FieldError :message="noteErrors.body" />
                </label>

                <div class="actions">
                  <button class="secondary-button" :disabled="busy" type="submit">{{ t('cases.addNote') }}</button>
                </div>
              </form>
            </PermissionGate>
          </BaseSection>
        </div>

        <AppAlert v-if="message" tone="success" :title="t('tasks.successTitle')" :message="message" />
        <AppAlert v-if="error" tone="error" :title="t('tasks.actionFailedTitle')" :message="error" />
      </aside>

      <main class="case-main-panel">
      <BaseSection :title="t('cases.listTitle')" :description="t('cases.listDescription')">
        <LoadingState v-if="casesLoading" :title="t('cases.loading')" />
        <AppAlert v-else-if="casesError" tone="error" :title="t('common.loadFailed')" :message="casesError" />
        <div v-else class="case-list">
          <article
            v-for="item in caseItems"
            :key="item.id"
            class="case-item"
            :style="{ '--row-accent': priorityColor(item.priority) }"
          >
            <div class="case-main">
              <div>
                <strong>{{ item.case_name }}</strong>
                <p>{{ scenarioLabel(item.case_type) }} · {{ item.owner || '-' }}</p>
              </div>
              <div class="badge-stack">
                <StatusBadge :label="labelValue(item.priority)" :tone="priorityTone(item.priority)" />
                <StatusBadge :label="labelValue(item.status)" :tone="caseStatusTone(item.status)" />
              </div>
            </div>
            <div class="case-summary">{{ item.summary || t('cases.noSummary') }}</div>
            <div class="actions">
              <button class="secondary-button" type="button" @click="inspectCase(item.id)">{{ t('cases.view') }}</button>
              <PermissionGate area="analysis" compact>
              <button class="secondary-button" type="button" @click="setCaseStatus(item.id, 'investigating')">
                {{ t('cases.investigate') }}
              </button>
              <button class="secondary-button" type="button" @click="setCaseStatus(item.id, 'ready_for_evidence')">
                {{ t('cases.readyForEvidence') }}
              </button>
              <button class="secondary-button" type="button" @click="setCaseStatus(item.id, 'closed')">{{ t('cases.close') }}</button>
              <button class="secondary-button destructive" type="button" @click="removeCase(item.id)">{{ t('cases.delete') }}</button>
              </PermissionGate>
            </div>
          </article>
          <EmptyState v-if="!caseItems.length" :title="t('cases.emptyTitle')" :description="t('cases.emptyDescription')" />
          <PaginationBar
            :total="caseTotal"
            :limit="filters.limit"
            :offset="filters.offset"
            :loading="casesLoading"
            @change="changeCasePage"
          />
        </div>
      </BaseSection>

    <BaseSection :title="t('cases.filterTitle')" :description="t('cases.filterDescription')">
      <form class="filter-form" @submit.prevent="applyFilters">
        <label class="field">
          <span>{{ t('tasks.search') }}</span>
          <input v-model="filters.q" :placeholder="t('cases.searchPlaceholder')" />
        </label>

        <label class="field">
          <span>{{ t('tasks.status') }}</span>
          <AppSelect
            v-model="filters.status"
            :options="[
              { value: '', label: t('signals.allStatuses') },
              { value: 'open', label: t('enum.open') },
              { value: 'investigating', label: t('enum.investigating') },
              { value: 'ready_for_evidence', label: t('enum.ready_for_evidence') },
              { value: 'closed', label: t('enum.closed') },
            ]"
          />
        </label>

        <label class="field">
          <span>{{ t('cases.priority') }}</span>
          <AppSelect
            v-model="filters.priority"
            :options="[
              { value: '', label: t('cases.allPriorities') },
              { value: 'critical', label: t('enum.critical') },
              { value: 'high', label: t('enum.high') },
              { value: 'medium', label: t('enum.medium') },
              { value: 'low', label: t('enum.low') },
            ]"
          />
        </label>

        <label class="field">
          <span>{{ t('cases.type') }}</span>
          <AppSelect
            v-model="filters.case_type"
            :options="[
              { value: '', label: t('signals.allTypes') },
              ...caseTypes.map((item) => ({ value: item, label: scenarioLabel(item) })),
            ]"
          />
        </label>

        <label class="field">
          <span>{{ t('cases.owner') }}</span>
          <input v-model="filters.owner" placeholder="analyst" />
        </label>

        <label class="field">
          <span>{{ t('tasks.limit') }}</span>
          <input v-model.number="filters.limit" min="1" max="500" step="1" type="number" />
        </label>

        <div class="actions filter-actions">
          <button class="primary-button" :disabled="casesLoading" type="submit">{{ t('tasks.apply') }}</button>
          <button class="secondary-button" :disabled="casesLoading" type="button" @click="clearFilters">{{ t('tasks.clear') }}</button>
        </div>
      </form>
    </BaseSection>

    <BaseSection :title="t('cases.detailTitle')" :description="selectedDetail ? selectedDetail.case.id : t('cases.detailDescription')">
      <div v-if="selectedDetail" class="detail-grid">
        <section class="detail-card">
          <h3>{{ selectedDetail.case.case_name }}</h3>
          <p>{{ selectedDetail.case.summary || t('cases.noSummary') }}</p>
          <div class="mini-grid">
            <span>{{ t('cases.linkCount', { count: selectedDetail.links.length }) }}</span>
            <span>{{ t('cases.noteCount', { count: selectedDetail.notes.length }) }}</span>
            <span>{{ t('cases.timelineCount', { count: selectedDetail.timeline.length }) }}</span>
            <span>{{ t('cases.auditCount', { count: selectedDetail.audit_events.length }) }}</span>
          </div>
          <form class="inline-evidence-form" @submit.prevent="generatePacketForSelectedCase">
            <PermissionGate area="analysis">
            <label class="field">
              <span>{{ t('cases.evidencePacketName') }}</span>
              <input v-model="evidenceForm.packet_name" :placeholder="t('cases.evidencePacketPlaceholder')" />
            </label>
            <button class="primary-button" :disabled="busy" type="submit">
              {{ busy ? t('cases.generating') : t('cases.generateEvidence') }}
            </button>
            </PermissionGate>
          </form>
        </section>

        <section class="detail-section evidence-tree-section">
          <h3>{{ t('cases.evidenceTree') }}</h3>
          <div class="evidence-tree">
            <div class="tree-root">
              <strong>{{ selectedDetail.case.case_name }}</strong>
              <span>{{ labelValue(selectedDetail.case.status) }} · {{ labelValue(selectedDetail.case.priority) }}</span>
            </div>
            <div class="tree-branches">
              <article v-for="branch in evidenceTree" :key="branch.key" class="tree-branch">
                <div class="branch-head">
                  <strong>{{ branch.title }}</strong>
                  <span>{{ branch.count }}</span>
                </div>
                <div class="branch-items">
                  <div v-for="item in branch.items" :key="item.id" class="tree-leaf">
                    <strong>{{ item.title }}</strong>
                    <span>{{ item.meta }}</span>
                  </div>
                  <EmptyState v-if="!branch.items.length" :title="t('cases.noObjects')" />
                </div>
              </article>
            </div>
          </div>
        </section>

        <section class="detail-section status-history-section">
          <div>
            <h3>{{ t('cases.statusHistory') }}</h3>
            <p class="muted">{{ t('cases.statusHistoryDescription') }}</p>
          </div>
          <div v-if="selectedDetail.status_history.length" class="status-history-list">
            <article
              v-for="item in selectedDetail.status_history"
              :key="item.source_event_id || `${item.new_status}-${item.changed_at}`"
              class="status-transition"
            >
              <div class="status-transition-main">
                <strong v-if="item.previous_status">
                  {{ labelValue(item.previous_status) }}
                  <span class="status-arrow" aria-hidden="true">→</span>
                  {{ labelValue(item.new_status) }}
                </strong>
                <strong v-else>{{ t('cases.statusInitial', { status: labelValue(item.new_status) }) }}</strong>
                <span>
                  {{ t('cases.statusChangedBy', { actor: item.actor_username || t('cases.systemActor') }) }}
                </span>
              </div>
              <StatusBadge :label="labelValue(item.new_status)" :tone="caseStatusTone(item.new_status)" />
              <time>{{ formatDate(item.changed_at) }}</time>
            </article>
          </div>
          <EmptyState
            v-else
            :title="t('cases.noStatusHistory')"
            :description="t('cases.noStatusHistoryDescription')"
          />
        </section>

        <section class="detail-section">
          <h3>{{ t('cases.linkedObjects') }}</h3>
          <article v-for="item in selectedDetail.links" :key="item.id" class="compact-item">
            <div>
              <strong>{{ item.label || item.target_id }}</strong>
              <span>{{ item.link_type }} · {{ item.target_id }}</span>
            </div>
            <PermissionGate area="analysis" compact>
            <button class="text-button" type="button" @click="removeLink(item.id)">{{ t('cases.remove') }}</button>
            </PermissionGate>
          </article>
          <EmptyState v-if="!selectedDetail.links.length" :title="t('cases.noLinkedObjects')" />
        </section>

        <section class="detail-section">
          <h3>{{ t('cases.note') }}</h3>
          <article v-for="item in selectedDetail.notes" :key="item.id" class="compact-item">
            <div>
              <strong>{{ item.author || t('cases.unknownAuthor') }} · {{ item.note_type }}</strong>
              <span>{{ item.body }}</span>
            </div>
            <PermissionGate area="analysis" compact>
            <button class="text-button" type="button" @click="removeNote(item.id)">{{ t('cases.remove') }}</button>
            </PermissionGate>
          </article>
          <EmptyState v-if="!selectedDetail.notes.length" :title="t('cases.noNotes')" />
        </section>

        <section class="detail-section">
          <h3>{{ t('cases.evidencePacks') }}</h3>
          <article v-for="item in selectedDetail.objects.evidence_packets" :key="item.id" class="compact-item">
            <div>
              <strong>{{ item.packet_name }}</strong>
              <span>{{ item.storage_uri }}</span>
            </div>
            <button
              class="text-button download"
              type="button"
              :disabled="downloadingEvidenceId === item.id"
              @click="downloadEvidence(item.id)"
            >
              {{ t('cases.download') }}
            </button>
          </article>
          <EmptyState v-if="!selectedDetail.objects.evidence_packets.length" :title="t('cases.noEvidencePacks')" />
        </section>

        <section class="detail-section timeline-section">
          <h3>{{ t('cases.timeline') }}</h3>
          <article v-for="item in selectedDetail.timeline" :key="`${item.event_type}-${item.target_id}-${item.event_time}`" class="timeline-item">
            <span>{{ formatDate(item.event_time) }}</span>
            <strong>{{ timelineTitle(item) }}</strong>
            <p>{{ timelineEventLabel(item.event_type) }} · {{ item.target_type }}</p>
          </article>
        </section>

        <section class="detail-section audit-section">
          <h3>{{ t('cases.audit') }}</h3>
          <article v-for="item in selectedDetail.audit_events" :key="item.id" class="audit-item">
            <div>
              <StatusBadge :label="auditActionLabel(item.action)" tone="info" />
              <strong>{{ item.summary }}</strong>
              <p>{{ item.actor_username }} · {{ item.actor_role }}</p>
            </div>
            <time>{{ formatDate(item.created_at) }}</time>
          </article>
          <EmptyState v-if="!selectedDetail.audit_events.length" :title="t('cases.noAuditEvents')" :description="t('cases.noAuditDescription')" />
        </section>
      </div>
      <EmptyState v-else :title="t('cases.noSelectionTitle')" :description="t('cases.noSelectionDescription')" />
    </BaseSection>
      </main>
    </div>
  </section>
</template>

<style scoped>
.page-grid,
.case-form,
.case-list,
.detail-section,
.timeline-section,
.filter-form {
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

.case-workspace {
  display: grid;
  grid-template-columns: minmax(320px, 390px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.case-side-panel {
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

.case-main-panel {
  min-width: 0;
  display: grid;
  gap: 18px;
}

.case-action-stack {
  display: grid;
  gap: 14px;
}

.case-side-panel .grid-two {
  grid-template-columns: 1fr;
}

.case-side-panel .actions {
  display: grid;
}

.case-side-panel .primary-button,
.case-side-panel .secondary-button {
  width: 100%;
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
.timeline-item p,
.tree-root span,
.tree-leaf span,
.tree-empty {
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
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-top: 14px;
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

.mini-grid span {
  border-radius: 12px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.86);
  font-weight: 700;
}

.inline-evidence-form {
  display: grid;
  gap: 12px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(226, 232, 240, 0.9);
}

.evidence-tree-section {
  grid-column: 1 / -1;
}

.status-history-section {
  grid-column: 1 / -1;
}

.status-history-list {
  display: grid;
  gap: 0;
  margin-left: 7px;
  border-left: 2px solid rgba(15, 118, 110, 0.24);
}

.status-transition {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(150px, auto);
  gap: 16px;
  align-items: center;
  padding: 4px 0 18px 24px;
}

.status-transition:last-child {
  padding-bottom: 4px;
}

.status-transition::before {
  position: absolute;
  top: 10px;
  left: -7px;
  width: 12px;
  height: 12px;
  border: 2px solid #ffffff;
  border-radius: 50%;
  background: var(--primary);
  box-shadow: 0 0 0 1px rgba(15, 118, 110, 0.3);
  content: '';
}

.status-transition-main {
  min-width: 0;
}

.status-transition-main strong,
.status-transition-main span {
  display: block;
}

.status-transition-main strong {
  overflow-wrap: anywhere;
}

.status-transition-main > span,
.status-transition time {
  margin-top: 4px;
  color: #64748b;
  font-size: 13px;
}

.status-transition time {
  margin-top: 0;
  text-align: right;
}

.status-arrow {
  display: inline;
  padding: 0 6px;
  color: var(--primary);
}

.evidence-tree {
  display: grid;
  gap: 14px;
}

.tree-root {
  display: grid;
  gap: 4px;
  justify-items: center;
  padding: 16px;
  border-radius: 16px;
  border: 1px solid rgba(37, 99, 235, 0.28);
  background: rgba(37, 99, 235, 0.08);
  color: #1e3a8a;
}

.tree-branches {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  align-items: start;
}

.tree-branch {
  display: grid;
  gap: 10px;
  min-height: 180px;
  padding: 12px;
  border-radius: 16px;
  border: 1px solid rgba(203, 213, 225, 0.9);
  background: rgba(255, 255, 255, 0.74);
}

.branch-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.9);
}

.branch-head span {
  border-radius: 999px;
  padding: 4px 8px;
  background: rgba(15, 118, 110, 0.1);
  color: var(--primary);
  font-size: 12px;
  font-weight: 800;
}

.branch-items {
  display: grid;
  gap: 8px;
}

.tree-leaf {
  display: grid;
  gap: 3px;
  padding: 9px;
  border-radius: 12px;
  background: rgba(248, 250, 252, 0.92);
}

.tree-leaf strong,
.tree-leaf span {
  overflow-wrap: anywhere;
}

.tree-empty {
  padding: 9px;
  font-size: 13px;
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

.compact-item,
.detail-card,
.timeline-item,
.audit-item {
  padding: 16px;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(248, 250, 252, 0.82);
}

.case-item {
  position: relative;
  overflow: hidden;
  padding: 16px 16px 16px 22px;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background:
    linear-gradient(90deg, color-mix(in oklch, var(--row-accent, #94a3b8) 7%, transparent), transparent 32%),
    rgba(252, 253, 254, 0.9);
  transition:
    transform 160ms ease,
    box-shadow 200ms ease,
    border-color 200ms ease;
}

.case-item::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: var(--row-accent, #94a3b8);
}

.case-item:hover {
  transform: translateY(-2px);
  border-color: color-mix(in oklch, var(--row-accent, var(--primary)) 40%, var(--border));
  box-shadow: 0 16px 32px -20px color-mix(in oklch, var(--row-accent, #1e40e6) 55%, transparent);
}

.case-main,
.compact-item,
.audit-item {
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
.audit-item p,
.detail-card p {
  margin: 0;
}

.audit-item {
  align-items: flex-start;
}

.audit-item strong {
  display: block;
  margin: 10px 0 4px;
}

.audit-item time {
  flex: 0 0 auto;
  color: #64748b;
  font-size: 13px;
  text-align: right;
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

.filter-actions {
  flex-wrap: nowrap;
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
  background: linear-gradient(135deg, #2563eb 0%, var(--primary) 100%);
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

.text-button.download {
  color: #2563eb;
  text-decoration: none;
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

  .case-workspace {
    grid-template-columns: 1fr;
  }

  .case-side-panel {
    position: static;
    max-height: none;
    overflow: visible;
    padding-right: 0;
  }

  .split-grid,
  .detail-grid,
  .grid-two,
  .mini-grid,
  .tree-branches,
  .filter-form {
    grid-template-columns: 1fr;
  }

  .status-transition {
    grid-template-columns: minmax(0, 1fr) auto;
  }

  .status-transition time {
    grid-column: 1 / -1;
    text-align: left;
  }
}
</style>
