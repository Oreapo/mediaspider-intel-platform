<script setup lang="ts">
import { computed, ref } from 'vue'
import { deleteReport, generateReport } from '../api/reports'
import { useCases } from '../composables/useCases'
import { useReports } from '../composables/useReports'
import type { Report } from '../types'

const { items: caseItems } = useCases()
const {
  items: reportItems,
  isLoading,
  error: loadError,
  fetchItems,
} = useReports()

const form = ref({
  case_id: '',
  report_name: '',
  report_type: 'investigation_brief',
})
const selectedReportId = ref('')
const isBusy = ref(false)
const message = ref('')
const error = ref('')

const selectedReport = computed<Report | undefined>(() =>
  reportItems.value.find((item) => item.id === selectedReportId.value),
)

const stats = computed(() => [
  { label: 'Reports', value: reportItems.value.length },
  { label: 'Generated', value: reportItems.value.filter((item) => item.status === 'generated').length },
  { label: 'Cases', value: new Set(reportItems.value.map((item) => item.case_id)).size },
  { label: 'Markdown', value: reportItems.value.filter((item) => item.storage_uri.endsWith('.md')).length },
])

async function submitReport() {
  isBusy.value = true
  message.value = ''
  error.value = ''
  try {
    const report = await generateReport({
      case_id: form.value.case_id,
      report_name: form.value.report_name,
      report_type: form.value.report_type,
    })
    selectedReportId.value = report.id
    message.value = 'Report generated.'
    form.value.report_name = ''
    await fetchItems()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    isBusy.value = false
  }
}

async function removeReport(reportId: string) {
  message.value = ''
  error.value = ''
  try {
    await deleteReport(reportId, true)
    if (selectedReportId.value === reportId) selectedReportId.value = ''
    message.value = 'Report deleted.'
    await fetchItems()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
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

    <section class="surface section-card">
      <div class="section-head">
        <div>
          <h2>Generate Report</h2>
          <p>从案件详情生成可审计的 Markdown 研判报告，保留信号 source refs。</p>
        </div>
      </div>

      <form class="report-form" @submit.prevent="submitReport">
        <div class="grid-two">
          <label class="field">
            <span>Case</span>
            <select v-model="form.case_id" required>
              <option value="" disabled>选择案件</option>
              <option v-for="item in caseItems" :key="item.id" :value="item.id">
                {{ item.case_name }} · {{ item.case_type }} · {{ item.priority }}
              </option>
            </select>
          </label>

          <label class="field">
            <span>Report Type</span>
            <select v-model="form.report_type">
              <option value="investigation_brief">investigation_brief</option>
              <option value="case_summary">case_summary</option>
              <option value="evidence_review">evidence_review</option>
            </select>
          </label>
        </div>

        <label class="field">
          <span>Report Name</span>
          <input v-model="form.report_name" required placeholder="例：导流链路研判报告" />
        </label>

        <div class="actions">
          <button class="primary-button" :disabled="isBusy" type="submit">
            {{ isBusy ? 'Generating...' : 'Generate Report' }}
          </button>
          <span v-if="message" class="success-text">{{ message }}</span>
          <span v-if="error" class="error-text">{{ error }}</span>
        </div>
      </form>
    </section>

    <section class="split-grid">
      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Report Registry</h2>
            <p>报告记录、下载文件和摘要统计。</p>
          </div>
        </div>

        <div v-if="isLoading" class="muted">Loading reports...</div>
        <div v-else-if="loadError" class="error-text">{{ loadError }}</div>
        <div v-else class="report-list">
          <article v-for="item in reportItems" :key="item.id" class="report-item">
            <div class="report-main">
              <div>
                <strong>{{ item.report_name }}</strong>
                <p>{{ item.report_type }} · {{ item.status }} · {{ item.storage_uri || '-' }}</p>
              </div>
              <span class="status-badge">{{ item.summary_json.signal_count || 0 }} signals</span>
            </div>
            <div class="report-meta">
              <span>{{ item.case_id }}</span>
              <span>{{ item.updated_at }}</span>
            </div>
            <div class="actions">
              <button class="secondary-button" type="button" @click="selectedReportId = item.id">Inspect</button>
              <a class="secondary-button link-button" :href="`/api/reports/${item.id}/download`">Download</a>
              <button class="secondary-button destructive" type="button" @click="removeReport(item.id)">Delete</button>
            </div>
          </article>
          <div v-if="!reportItems.length" class="muted">No reports yet.</div>
        </div>
      </section>

      <section class="surface section-card preview-card">
        <div class="section-head">
          <div>
            <h2>Report Preview</h2>
            <p v-if="selectedReport">{{ selectedReport.report_name }}</p>
            <p v-else>选择一份报告查看 Markdown 内容。</p>
          </div>
        </div>
        <pre v-if="selectedReport">{{ selectedReport.content_markdown }}</pre>
        <div v-else class="muted">No report selected.</div>
      </section>
    </section>
  </section>
</template>

<style scoped>
.page-grid,
.report-form,
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
.field select {
  width: 100%;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid rgba(203, 213, 225, 0.95);
  background: rgba(255, 255, 255, 0.94);
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

  .split-grid,
  .grid-two {
    grid-template-columns: 1fr;
  }

  .report-main {
    display: grid;
  }
}
</style>
