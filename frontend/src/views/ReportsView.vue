<script setup lang="ts">
import { computed, ref } from 'vue'
import { deleteReport, downloadReport, generateReport, updateReport } from '../api/reports'
import AppAlert from '../components/ui/AppAlert.vue'
import BaseSection from '../components/ui/BaseSection.vue'
import EmptyState from '../components/ui/EmptyState.vue'
import FieldError from '../components/ui/FieldError.vue'
import LoadingState from '../components/ui/LoadingState.vue'
import PaginationBar from '../components/ui/PaginationBar.vue'
import PermissionGate from '../components/ui/PermissionGate.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import { useCases } from '../composables/useCases'
import { useI18n } from '../composables/useI18n'
import { useReports } from '../composables/useReports'
import { requestConfirm } from '../lib/confirm'
import { lastPageOffset } from '../lib/pagination'
import { required, type ValidationErrors } from '../lib/validation'
import type { Report } from '../types'

const { items: caseItems } = useCases()
const reportLimit = 12
const reportOffset = ref(0)
const {
  items: reportItems,
  total: reportTotal,
  isLoading,
  error: loadError,
  fetchItems,
} = useReports({ limit: reportLimit, offset: 0 })
const { t } = useI18n()

const form = ref({
  case_id: '',
  report_name: '',
  report_type: 'investigation_brief',
})
const selectedReportId = ref('')
const editorForm = ref({
  report_name: '',
  status: 'generated',
  content_markdown: '',
})
const isBusy = ref(false)
const downloadingReportId = ref('')
const message = ref('')
const error = ref('')
const formErrors = ref<ValidationErrors>({})
const editorErrors = ref<ValidationErrors>({})

const selectedReport = computed<Report | undefined>(() =>
  reportItems.value.find((item) => item.id === selectedReportId.value),
)

const stats = computed(() => [
  { label: t('reports.statsReports'), value: reportTotal.value },
  { label: t('reports.statsGenerated'), value: reportItems.value.filter((item) => item.status === 'generated').length },
  { label: t('reports.statsCases'), value: new Set(reportItems.value.map((item) => item.case_id)).size },
  { label: t('reports.statsMarkdown'), value: reportItems.value.filter((item) => item.storage_uri.endsWith('.md')).length },
])

async function fetchReportPage(offset = reportOffset.value) {
  reportOffset.value = offset
  await fetchItems({ limit: reportLimit, offset })
  const normalizedOffset = lastPageOffset(reportTotal.value, reportLimit)
  if (reportOffset.value > normalizedOffset) {
    reportOffset.value = normalizedOffset
    if (reportTotal.value > 0) {
      await fetchItems({ limit: reportLimit, offset: normalizedOffset })
    }
  }
}

async function changeReportPage(offset: number) {
  selectedReportId.value = ''
  await fetchReportPage(offset)
}

function validateGenerateForm() {
  const errors: ValidationErrors = {}
  const caseError = required(form.value.case_id, t('cases.case'))
  const nameError = required(form.value.report_name, t('reports.name'))

  if (caseError) errors.case_id = caseError
  if (nameError) errors.report_name = nameError

  formErrors.value = errors
  return Object.keys(errors).length === 0
}

function validateEditorForm() {
  const errors: ValidationErrors = {}
  const nameError = required(editorForm.value.report_name, t('reports.name'))
  const contentError = required(editorForm.value.content_markdown, t('reports.markdownContent'))

  if (nameError) errors.report_name = nameError
  if (contentError) errors.content_markdown = contentError

  editorErrors.value = errors
  return Object.keys(errors).length === 0
}

async function submitReport() {
  message.value = ''
  error.value = ''
  if (!validateGenerateForm()) {
    error.value = t('reports.fixGenerateErrors')
    return
  }

  isBusy.value = true
  try {
    const report = await generateReport({
      case_id: form.value.case_id,
      report_name: form.value.report_name,
      report_type: form.value.report_type,
    })
    selectedReportId.value = report.id
    message.value = t('reports.generatedMessage')
    form.value.report_name = ''
    await fetchReportPage(0)
    selectReport(report)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    isBusy.value = false
  }
}

function selectReport(report: Report) {
  selectedReportId.value = report.id
  editorForm.value = {
    report_name: report.report_name,
    status: report.status,
    content_markdown: report.content_markdown,
  }
}

async function saveReport() {
  if (!selectedReport.value) return
  message.value = ''
  error.value = ''
  if (!validateEditorForm()) {
    error.value = t('reports.fixEditorErrors')
    return
  }

  isBusy.value = true
  try {
    const report = await updateReport(selectedReport.value.id, {
      report_name: editorForm.value.report_name,
      status: editorForm.value.status,
      content_markdown: editorForm.value.content_markdown,
    })
    message.value = t('reports.savedMessage')
    await fetchReportPage()
    selectReport(report)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    isBusy.value = false
  }
}

async function removeReport(reportId: string) {
  const confirmed = await requestConfirm({
    title: t('reports.deleteTitle'),
    message: t('reports.deleteMessage'),
    confirmLabel: t('reports.deleteConfirm'),
  })
  if (!confirmed) return

  message.value = ''
  error.value = ''
  try {
    await deleteReport(reportId, true)
    if (selectedReportId.value === reportId) selectedReportId.value = ''
    message.value = t('reports.deletedMessage')
    await fetchReportPage()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function downloadReportFile(reportId: string) {
  message.value = ''
  error.value = ''
  downloadingReportId.value = reportId
  try {
    await downloadReport(reportId)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    downloadingReportId.value = ''
  }
}

function labelValue(value: string) {
  const key = `enum.${value}`
  const translated = t(key)
  return translated === key ? value : translated
}

function reportTypeLabel(value: string) {
  const key = `reportType.${value}`
  const translated = t(key)
  return translated === key ? value : translated
}

function scenarioLabel(value: string) {
  const key = `scenario.${value}`
  const translated = t(key)
  return translated === key ? value : translated
}

function reportSignalCount(report: Report) {
  const value = report.summary_json.signal_count
  return typeof value === 'number' ? value : 0
}
</script>

<template>
  <section class="page-grid">
    <div class="stats-grid">
      <article v-for="stat in stats" :key="stat.label" class="surface stat-card">
        <span>{{ stat.label }}</span>
        <strong>{{ stat.value }}</strong>
      </article>
    </div>

    <div class="report-workspace">
      <aside class="report-side-panel">
        <BaseSection compact :title="t('reports.generateTitle')" :description="t('reports.generateDescription')">
      <PermissionGate area="analysis">
      <form class="report-form" @submit.prevent="submitReport">
        <div class="grid-two">
          <label class="field">
            <span>{{ t('cases.case') }}</span>
            <select v-model="form.case_id" required>
              <option value="" disabled>{{ t('cases.chooseCase') }}</option>
              <option v-for="item in caseItems" :key="item.id" :value="item.id">
                {{ item.case_name }} · {{ scenarioLabel(item.case_type) }} · {{ labelValue(item.priority) }}
              </option>
            </select>
            <FieldError :message="formErrors.case_id" />
          </label>

          <label class="field">
            <span>{{ t('reports.type') }}</span>
            <select v-model="form.report_type">
              <option value="investigation_brief">{{ t('reportType.investigation_brief') }}</option>
              <option value="case_summary">{{ t('reportType.case_summary') }}</option>
              <option value="evidence_review">{{ t('reportType.evidence_review') }}</option>
            </select>
          </label>
        </div>

        <label class="field">
          <span>{{ t('reports.name') }}</span>
          <input v-model="form.report_name" required :placeholder="t('reports.namePlaceholder')" />
          <FieldError :message="formErrors.report_name" />
        </label>

        <div class="actions">
          <button class="primary-button" :disabled="isBusy" type="submit">
            {{ isBusy ? t('reports.generating') : t('reports.generate') }}
          </button>
        </div>
      </form>
      </PermissionGate>
    </BaseSection>

        <AppAlert v-if="message" tone="success" :title="t('tasks.successTitle')" :message="message" />
        <AppAlert v-if="error" tone="error" :title="t('tasks.actionFailedTitle')" :message="error" />
      </aside>

      <main class="report-main-panel">

    <section class="split-grid">
      <BaseSection :title="t('reports.listTitle')" :description="t('reports.listDescription')">
        <LoadingState v-if="isLoading" :title="t('reports.loading')" />
        <AppAlert v-else-if="loadError" tone="error" :title="t('common.loadFailed')" :message="loadError" />
        <div v-else class="report-list">
          <article v-for="item in reportItems" :key="item.id" class="report-item">
            <div class="report-main">
              <div>
                <strong>{{ item.report_name }}</strong>
                <p>{{ reportTypeLabel(item.report_type) }} · {{ labelValue(item.status) }} · {{ item.storage_uri || '-' }}</p>
              </div>
              <StatusBadge :label="t('reports.signalCount', { count: reportSignalCount(item) })" tone="info" />
            </div>
            <div class="report-meta">
              <span>{{ item.case_id }}</span>
              <span>{{ item.updated_at }}</span>
            </div>
            <div class="actions">
              <button class="secondary-button" type="button" @click="selectReport(item)">{{ t('reports.edit') }}</button>
              <button
                class="secondary-button"
                type="button"
                :disabled="downloadingReportId === item.id"
                @click="downloadReportFile(item.id)"
              >
                {{ t('cases.download') }}
              </button>
              <PermissionGate area="analysis" compact>
              <button class="secondary-button destructive" type="button" @click="removeReport(item.id)">{{ t('cases.delete') }}</button>
              </PermissionGate>
            </div>
          </article>
          <EmptyState v-if="!reportItems.length" :title="t('reports.emptyTitle')" :description="t('reports.emptyDescription')" />
          <PaginationBar
            :total="reportTotal"
            :limit="reportLimit"
            :offset="reportOffset"
            :loading="isLoading"
            @change="changeReportPage"
          />
        </div>
      </BaseSection>

      <BaseSection
        class="preview-card"
        :title="t('reports.editorTitle')"
        :description="selectedReport ? selectedReport.report_name : t('reports.editorDescription')"
      >
        <PermissionGate v-if="selectedReport" area="analysis">
        <form v-if="selectedReport" class="editor-form" @submit.prevent="saveReport">
          <div class="grid-two">
            <label class="field">
              <span>{{ t('reports.name') }}</span>
              <input v-model="editorForm.report_name" required />
              <FieldError :message="editorErrors.report_name" />
            </label>
            <label class="field">
              <span>{{ t('reports.status') }}</span>
              <select v-model="editorForm.status">
                <option value="draft">{{ t('enum.draft') }}</option>
                <option value="generated">{{ t('enum.generated') }}</option>
                <option value="archived">{{ t('enum.archived') }}</option>
              </select>
            </label>
          </div>
          <label class="field">
            <span>{{ t('reports.markdownContent') }}</span>
            <textarea v-model="editorForm.content_markdown" rows="18" />
            <FieldError :message="editorErrors.content_markdown" />
          </label>
          <div class="actions">
            <button class="primary-button" :disabled="isBusy" type="submit">
              {{ isBusy ? t('reports.saving') : t('reports.save') }}
            </button>
          </div>
        </form>
        </PermissionGate>
        <EmptyState v-else :title="t('reports.noSelectionTitle')" :description="t('reports.noSelectionDescription')" />
      </BaseSection>
    </section>

    <BaseSection v-if="selectedReport" class="preview-card" :title="t('reports.previewTitle')" :description="t('reports.previewDescription')">
      <pre>{{ editorForm.content_markdown }}</pre>
    </BaseSection>
      </main>
    </div>
  </section>
</template>

<style scoped>
.page-grid,
.report-form,
.editor-form,
.report-list {
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
  grid-template-columns: minmax(320px, 0.9fr) minmax(0, 1.2fr);
  gap: 18px;
}

.report-workspace {
  display: grid;
  grid-template-columns: minmax(320px, 390px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.report-side-panel {
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

.report-main-panel {
  min-width: 0;
  display: grid;
  gap: 18px;
}

.report-side-panel .grid-two {
  grid-template-columns: 1fr;
}

.report-side-panel .actions {
  display: grid;
}

.report-side-panel .primary-button,
.report-side-panel .secondary-button {
  width: 100%;
}

.section-card,
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
.report-item p,
.report-meta,
.stat-card span {
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
.field select,
.field textarea {
  width: 100%;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid rgba(203, 213, 225, 0.95);
  background: rgba(255, 255, 255, 0.94);
}

.field textarea {
  min-height: 360px;
  resize: vertical;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.report-item {
  padding: 16px;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(248, 250, 252, 0.82);
}

.report-main {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.report-main strong {
  display: block;
  margin-bottom: 4px;
}

.report-main p {
  margin: 0;
}

.report-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin: 12px 0;
  font-size: 13px;
}

.status-badge {
  height: fit-content;
  border-radius: 999px;
  padding: 6px 10px;
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
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

.link-button {
  display: inline-flex;
  text-decoration: none;
}

.secondary-button.destructive {
  background: rgba(254, 226, 226, 0.95);
  color: #b91c1c;
}

.preview-card {
  min-width: 0;
}

pre {
  max-height: 660px;
  margin: 0;
  padding: 16px;
  overflow: auto;
  border-radius: 16px;
  background: #0f172a;
  color: #e2e8f0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
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

  .report-workspace {
    grid-template-columns: 1fr;
  }

  .report-side-panel {
    position: static;
    max-height: none;
    overflow: visible;
    padding-right: 0;
  }

  .split-grid,
  .grid-two {
    grid-template-columns: 1fr;
  }

  .report-main {
    display: grid;
  }
}
</style>
