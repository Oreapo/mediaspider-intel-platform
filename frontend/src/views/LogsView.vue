<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getRunLog, listAuditEvents, listRunLogs } from '../api/logs'
import AppAlert from '../components/ui/AppAlert.vue'
import BaseSection from '../components/ui/BaseSection.vue'
import EmptyState from '../components/ui/EmptyState.vue'
import LoadingState from '../components/ui/LoadingState.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import { useI18n } from '../composables/useI18n'
import type { AuditEvent, RunLogDetail, RunLogEntry } from '../types'

const { t } = useI18n()
const entries = ref<RunLogEntry[]>([])
const auditEvents = ref<AuditEvent[]>([])
const selected = ref<RunLogDetail | null>(null)
const activeTab = ref<'runs' | 'audit'>('runs')
const isLoading = ref(false)
const isLoadingAudit = ref(false)
const isLoadingLog = ref(false)
const error = ref('')
const auditError = ref('')
const logError = ref('')
const auditFilters = ref({
  q: '',
  targetType: '',
  targetId: '',
  actorUsername: '',
  action: '',
  createdFrom: '',
  createdTo: '',
})

const successfulRuns = computed(() => entries.value.filter((item) => item.run.status === 'succeeded').length)
const failedRuns = computed(() => entries.value.filter((item) => item.run.status === 'failed').length)
const runsWithLogs = computed(() => entries.value.filter((item) => item.has_log).length)

async function fetchEntries() {
  isLoading.value = true
  error.value = ''
  try {
    entries.value = await listRunLogs()
    if (!selected.value && entries.value.length) {
      await selectRun(entries.value[0])
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    isLoading.value = false
  }
}

async function selectRun(entry: RunLogEntry) {
  selected.value = null
  logError.value = ''
  if (!entry.has_log) {
    logError.value = t('logs.noReadableLog')
    return
  }
  isLoadingLog.value = true
  try {
    selected.value = await getRunLog(entry.run.id)
  } catch (err) {
    logError.value = err instanceof Error ? err.message : String(err)
  } finally {
    isLoadingLog.value = false
  }
}

function formatBytes(size: number) {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

async function fetchAuditEvents() {
  isLoadingAudit.value = true
  auditError.value = ''
  try {
    auditEvents.value = await listAuditEvents(auditFilters.value)
  } catch (err) {
    auditError.value = err instanceof Error ? err.message : String(err)
  } finally {
    isLoadingAudit.value = false
  }
}

async function clearAuditFilters() {
  auditFilters.value = {
    q: '',
    targetType: '',
    targetId: '',
    actorUsername: '',
    action: '',
    createdFrom: '',
    createdTo: '',
  }
  await fetchAuditEvents()
}

function runTone(status: string) {
  if (status === 'succeeded') return 'success'
  if (status === 'running') return 'info'
  if (status === 'failed') return 'danger'
  return 'neutral'
}

function formatDate(value: string | null) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function actionLabel(action: string) {
  const key = `auditAction.${action}`
  const translated = t(key)
  return translated === key ? action : translated
}

function labelValue(value: string) {
  const key = `enum.${value}`
  const translated = t(key)
  return translated === key ? value : translated
}

onMounted(() => {
  fetchEntries()
  fetchAuditEvents()
})
</script>

<template>
  <section class="page-grid">
    <BaseSection :title="t('logs.title')" :description="t('logs.description')">
      <template #actions>
        <button class="secondary-button" type="button" @click="activeTab === 'runs' ? fetchEntries() : fetchAuditEvents()">{{ t('logs.refresh') }}</button>
      </template>

      <div class="stats-grid">
        <div class="stat-item">
          <span>{{ t('logs.totalRuns') }}</span>
          <strong>{{ entries.length }}</strong>
        </div>
        <div class="stat-item">
          <span>{{ t('logs.success') }}</span>
          <strong>{{ successfulRuns }}</strong>
        </div>
        <div class="stat-item">
          <span>{{ t('logs.failed') }}</span>
          <strong>{{ failedRuns }}</strong>
        </div>
        <div class="stat-item">
          <span>{{ t('logs.logs') }}</span>
          <strong>{{ runsWithLogs }}</strong>
        </div>
        <div class="stat-item">
          <span>{{ t('logs.auditEvents') }}</span>
          <strong>{{ auditEvents.length }}</strong>
        </div>
      </div>

      <div class="tab-strip" role="tablist" :aria-label="t('logs.tabAria')">
        <button :class="{ active: activeTab === 'runs' }" type="button" @click="activeTab = 'runs'">{{ t('logs.runTab') }}</button>
        <button :class="{ active: activeTab === 'audit' }" type="button" @click="activeTab = 'audit'">{{ t('logs.auditTab') }}</button>
      </div>
    </BaseSection>

    <section v-if="activeTab === 'runs'" class="content-grid">
      <BaseSection :title="t('logs.runHistoryTitle')" :description="t('logs.runHistoryDescription')">
        <LoadingState v-if="isLoading" :title="t('logs.loadingLogs')" />
        <AppAlert v-else-if="error" tone="error" :title="t('common.loadFailed')" :message="error" />
        <div v-else class="run-list">
          <button
            v-for="entry in entries"
            :key="entry.run.id"
            class="run-item"
            type="button"
            @click="selectRun(entry)"
          >
            <StatusBadge :label="labelValue(entry.run.status)" :tone="runTone(entry.run.status)" />
            <strong>{{ entry.run.task_id }}</strong>
            <span>{{ formatDate(entry.run.started_at) }}</span>
            <span>{{ entry.has_log ? formatBytes(entry.log_size) : t('logs.noLog') }}</span>
          </button>
          <EmptyState v-if="!entries.length" :title="t('logs.noRunsTitle')" :description="t('logs.noRunsDescription')" />
        </div>
      </BaseSection>

      <BaseSection
        class="log-card"
        :title="t('logs.outputTitle')"
        :description="selected ? `${selected.run.id} · ${selected.line_count} lines` : t('logs.outputDescription')"
      >
        <LoadingState v-if="isLoadingLog" :title="t('logs.loadingLogs')" />
        <AppAlert v-else-if="logError" tone="warning" :title="t('logs.unreadableTitle')" :message="logError" />
        <pre v-else-if="selected" class="log-output">{{ selected.content }}</pre>
        <EmptyState v-else :title="t('logs.noSelectionTitle')" :description="t('logs.noSelectionDescription')" />
      </BaseSection>
    </section>

    <BaseSection v-else :title="t('logs.auditTitle')" :description="t('logs.auditDescription')">
      <form class="audit-filter" @submit.prevent="fetchAuditEvents">
        <input v-model="auditFilters.q" :placeholder="t('logs.auditSearchPlaceholder')" />
        <input v-model="auditFilters.targetType" :placeholder="t('logs.targetTypePlaceholder')" />
        <input v-model="auditFilters.targetId" :placeholder="t('logs.targetIdPlaceholder')" />
        <input v-model="auditFilters.actorUsername" :placeholder="t('logs.actorPlaceholder')" />
        <input v-model="auditFilters.action" :placeholder="t('logs.actionPlaceholder')" />
        <input v-model="auditFilters.createdFrom" type="datetime-local" />
        <input v-model="auditFilters.createdTo" type="datetime-local" />
        <button class="secondary-button" type="submit">{{ t('logs.filter') }}</button>
        <button class="secondary-button" type="button" @click="clearAuditFilters">{{ t('tasks.clear') }}</button>
      </form>
      <LoadingState v-if="isLoadingAudit" :title="t('logs.loadingAudit')" />
      <AppAlert v-else-if="auditError" tone="error" :title="t('common.loadFailed')" :message="auditError" />
      <div v-else class="audit-list">
        <article v-for="event in auditEvents" :key="event.id" class="audit-item">
          <div>
            <StatusBadge :label="actionLabel(event.action)" tone="info" />
            <h3>{{ event.summary }}</h3>
            <p>{{ event.target_type }} / {{ event.target_id }}</p>
          </div>
          <div class="audit-meta">
            <strong>{{ event.actor_username }}</strong>
            <span>{{ event.actor_role }}</span>
            <time>{{ formatDate(event.created_at) }}</time>
          </div>
        </article>
        <EmptyState v-if="!auditEvents.length" :title="t('logs.noAuditTitle')" :description="t('logs.noAuditDescription')" />
      </div>
    </BaseSection>
  </section>
</template>

<style scoped>
.page-grid,
.run-list,
.audit-list {
  display: grid;
  gap: 16px;
}

.section-card {
  border-radius: 24px;
  padding: 22px;
}

.section-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
}

.section-head.compact {
  margin-bottom: 12px;
}

.section-head h2 {
  margin: 0 0 6px;
}

.section-head p,
.muted,
.run-item span,
.stat-item span {
  color: #64748b;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.stat-item {
  display: grid;
  gap: 6px;
  padding: 14px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 16px;
  background: rgba(248, 250, 252, 0.82);
}

.stat-item strong {
  font-size: 24px;
}

.tab-strip {
  display: inline-grid;
  grid-template-columns: repeat(2, minmax(120px, 1fr));
  gap: 4px;
  margin-top: 16px;
  padding: 4px;
  border: 1px solid rgba(203, 213, 225, 0.86);
  border-radius: 12px;
  background: rgba(248, 250, 252, 0.78);
}

.tab-strip button {
  border: none;
  border-radius: 9px;
  padding: 9px 12px;
  background: transparent;
  color: #475569;
  font-weight: 800;
  cursor: pointer;
}

.tab-strip button.active {
  background: #ffffff;
  color: #0f172a;
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.08);
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(280px, 0.9fr) minmax(0, 1.4fr);
  gap: 16px;
}

.audit-filter {
  display: grid;
  grid-template-columns: minmax(220px, 1.4fr) repeat(4, minmax(120px, 1fr)) minmax(160px, 1fr) minmax(160px, 1fr) auto auto;
  gap: 10px;
  align-items: center;
  margin-bottom: 16px;
}

.audit-filter input {
  width: 100%;
  min-height: 42px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(203, 213, 225, 0.95);
  background: rgba(255, 255, 255, 0.94);
}

.run-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 6px 10px;
  padding: 14px;
  text-align: left;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 16px;
  background: rgba(248, 250, 252, 0.82);
  cursor: pointer;
}

.run-item strong {
  overflow-wrap: anywhere;
}

.audit-item {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 16px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 16px;
  background: rgba(248, 250, 252, 0.82);
}

.audit-item h3 {
  margin: 10px 0 6px;
  font-size: 16px;
}

.audit-item p,
.audit-meta span,
.audit-meta time {
  margin: 0;
  color: #64748b;
}

.audit-meta {
  display: grid;
  gap: 4px;
  min-width: 180px;
  text-align: right;
}

.status-badge {
  width: fit-content;
  padding: 5px 9px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.secondary-button {
  border: none;
  border-radius: 12px;
  padding: 10px 14px;
  background: rgba(226, 232, 240, 0.9);
  color: #1e293b;
  font-weight: 700;
  cursor: pointer;
}

.log-card {
  min-width: 0;
}

.log-output {
  min-height: 420px;
  max-height: 640px;
  margin: 0;
  padding: 16px;
  overflow: auto;
  border-radius: 16px;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 13px;
  line-height: 1.55;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.error-text {
  color: #dc2626;
}

@media (max-width: 960px) {
  .stats-grid,
  .content-grid,
  .audit-filter {
    grid-template-columns: 1fr;
  }

  .section-head {
    display: grid;
  }

  .audit-item {
    display: grid;
  }

  .audit-meta {
    min-width: 0;
    text-align: left;
  }
}
</style>
