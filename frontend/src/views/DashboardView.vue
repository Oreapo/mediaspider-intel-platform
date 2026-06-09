<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useDashboardSummary } from '../composables/useDashboardSummary'
import { useI18n } from '../composables/useI18n'
import { usePlatformModels } from '../composables/usePlatformModels'

const { items: platformItems, isLoading: platformsLoading, error: platformsError } = usePlatformModels()
const { summary, isLoading, error } = useDashboardSummary()
const { t } = useI18n()

const data = computed(() => summary.value)

const stats = computed(() => [
  {
    label: t('dashboard.highRiskSignals'),
    value: data.value?.summary.high_risk_signal_count ?? 0,
    hint: t('dashboard.highRiskHint'),
    tone: 'high',
  },
  {
    label: t('dashboard.openCases'),
    value: data.value?.summary.open_case_count ?? 0,
    hint: t('dashboard.totalCases', { count: data.value?.summary.case_count ?? 0 }),
    tone: 'open',
  },
  {
    label: t('dashboard.datasets'),
    value: data.value?.summary.dataset_count ?? 0,
    hint: t('dashboard.records', { count: data.value?.summary.record_count ?? 0 }),
    tone: 'datasets',
  },
  {
    label: t('dashboard.evidencePacks'),
    value: data.value?.summary.evidence_packet_count ?? 0,
    hint: t('dashboard.exportableMaterials'),
    tone: 'evidence',
  },
])

const operationalStats = computed(() => [
  { label: t('dashboard.tasks'), value: data.value?.summary.task_count ?? 0 },
  { label: t('dashboard.runs'), value: data.value?.summary.task_run_count ?? 0 },
  { label: t('dashboard.analysis'), value: data.value?.summary.analysis_job_count ?? 0 },
  { label: t('dashboard.entities'), value: data.value?.summary.entity_count ?? 0 },
  { label: t('dashboard.relations'), value: data.value?.summary.relation_count ?? 0 },
  { label: t('dashboard.confirmedSignals'), value: data.value?.summary.confirmed_signal_count ?? 0 },
])

const signalRiskRows = computed(() =>
  orderBreakdown(data.value?.breakdowns.signal_risk_levels, ['critical', 'high', 'medium', 'low']),
)
const signalStatusRows = computed(() =>
  orderBreakdown(data.value?.breakdowns.signal_statuses, ['new', 'reviewing', 'confirmed', 'dismissed']),
)
const casePriorityRows = computed(() =>
  orderBreakdown(data.value?.breakdowns.case_priorities, ['critical', 'high', 'medium', 'low']),
)
const caseStatusRows = computed(() =>
  orderBreakdown(data.value?.breakdowns.case_statuses, ['open', 'investigating', 'ready_for_evidence', 'closed']),
)
const platformRiskRows = computed(() => data.value?.risk_distribution.platforms ?? [])
const scenarioRiskRows = computed(() => data.value?.risk_distribution.scenarios ?? [])
const signalRiskChartRows = computed(() => toChartRows(signalRiskRows.value))
const signalStatusChartRows = computed(() => toChartRows(signalStatusRows.value))
const casePriorityChartRows = computed(() => toChartRows(casePriorityRows.value))
const caseStatusChartRows = computed(() => toChartRows(caseStatusRows.value))
const signalRiskTotal = computed(() => sumRows(signalRiskRows.value))
const signalStatusTotal = computed(() => sumRows(signalStatusRows.value))
const casePriorityTotal = computed(() => sumRows(casePriorityRows.value))
const caseStatusTotal = computed(() => sumRows(caseStatusRows.value))
const signalRiskDonutStyle = computed(() => donutStyle(signalRiskChartRows.value, signalRiskTotal.value))
const topPlatformRiskRows = computed(() => platformRiskRows.value.slice(0, 5))
const topScenarioRiskRows = computed(() => scenarioRiskRows.value.slice(0, 5))
const platformRiskMax = computed(() =>
  Math.max(...topPlatformRiskRows.value.map((row) => row.high_risk_signal_count), 1),
)
const scenarioRiskMax = computed(() =>
  Math.max(...topScenarioRiskRows.value.map((row) => row.high_risk_signal_count), 1),
)
const pipelineRows = computed(() => [
  { label: t('dashboard.tasks'), value: data.value?.summary.task_count ?? 0, tone: 'tasks' },
  { label: t('dashboard.datasets'), value: data.value?.summary.dataset_count ?? 0, tone: 'datasets' },
  { label: t('dashboard.signals'), value: data.value?.summary.signal_count ?? 0, tone: 'signals' },
  { label: t('dashboard.entities'), value: data.value?.summary.entity_count ?? 0, tone: 'entities' },
  { label: t('dashboard.cases'), value: data.value?.summary.case_count ?? 0, tone: 'cases' },
  { label: t('dashboard.evidencePacks'), value: data.value?.summary.evidence_packet_count ?? 0, tone: 'evidence' },
])
const pipelineMax = computed(() => Math.max(...pipelineRows.value.map((row) => row.value), 1))
const pendingSignals = computed(() => data.value?.pending.high_risk_signals ?? [])
const failedRuns = computed(() => data.value?.pending.failed_runs ?? [])
const readyCases = computed(() => data.value?.pending.ready_cases ?? [])
const latestTasks = computed(() => data.value?.latest.tasks ?? [])
const latestSignals = computed(() => data.value?.latest.signals ?? [])
const latestCases = computed(() => data.value?.latest.cases ?? [])
const latestEvidencePackets = computed(() => data.value?.latest.evidence_packets ?? [])

const healthCards = computed(() => [
  {
    label: t('dashboard.collectionHealth'),
    value: t('dashboard.taskCount', { count: data.value?.summary.task_count ?? 0 }),
    hint: failedRuns.value.length
      ? t('dashboard.failedRunsPending', { count: failedRuns.value.length })
      : t('dashboard.collectionStable'),
    tone: failedRuns.value.length ? 'danger' : 'good',
  },
  {
    label: t('dashboard.reviewPressure'),
    value: t('dashboard.pendingSignals', { count: pendingSignals.value.length }),
    hint: t('dashboard.highRiskSignalCount', { count: data.value?.summary.high_risk_signal_count ?? 0 }),
    tone: pendingSignals.value.length ? 'warning' : 'good',
  },
  {
    label: t('dashboard.caseProgress'),
    value: t('dashboard.openCaseCount', { count: data.value?.summary.open_case_count ?? 0 }),
    hint: t('dashboard.readyCaseCount', { count: readyCases.value.length }),
    tone: readyCases.value.length ? 'warning' : 'neutral',
  },
])

const boardColumns = computed(() => [
  {
    key: 'collection',
    title: t('dashboard.collectionQueue'),
    subtitle: t('dashboard.collectionQueueSubtitle'),
    to: '/tasks',
    empty: t('dashboard.noCollectionTasks'),
    items: [
      ...failedRuns.value.map((run) => ({
        id: `run-${run.id}`,
        title: run.task_id,
        meta: `${t('dashboard.runFailed')} · ${run.error_message || run.finished_at || '-'}`,
        badge: t('dashboard.toInvestigate'),
        tone: 'danger',
      })),
      ...latestTasks.value.slice(0, 4).map((task) => ({
        id: `task-${task.id}`,
        title: task.task_name,
        meta: `${task.platform} · ${labelValue(task.status)} · ${task.task_mode}`,
        badge: labelValue(task.status),
        tone: task.status === 'enabled' ? 'good' : 'neutral',
      })),
    ].slice(0, 5),
  },
  {
    key: 'review',
    title: t('dashboard.reviewQueue'),
    subtitle: t('dashboard.reviewQueueSubtitle'),
    to: '/signals',
    empty: t('dashboard.noReviewSignals'),
    items: [
      ...pendingSignals.value.map((signal) => ({
        id: `pending-${signal.id}`,
        title: signal.summary,
        meta: `${labelValue(signal.risk_level)}${t('dashboard.riskSuffix')} · ${t('dashboard.score', { score: signal.risk_score })}`,
        badge: labelValue(signal.status),
        tone: ['critical', 'high'].includes(signal.risk_level) ? 'danger' : 'warning',
      })),
      ...latestSignals.value.slice(0, 3).map((signal) => ({
        id: `signal-${signal.id}`,
        title: signal.summary,
        meta: `${signal.signal_type} · ${labelValue(signal.risk_level)}${t('dashboard.riskSuffix')}`,
        badge: labelValue(signal.status),
        tone: signal.status === 'confirmed' ? 'good' : 'neutral',
      })),
    ].slice(0, 5),
  },
  {
    key: 'casework',
    title: t('dashboard.casework'),
    subtitle: t('dashboard.caseworkSubtitle'),
    to: '/cases',
    empty: t('dashboard.noOpenCases'),
    items: [
      ...readyCases.value.map((caseItem) => ({
        id: `ready-${caseItem.id}`,
        title: caseItem.case_name,
        meta: `${labelValue(caseItem.priority)}${t('dashboard.prioritySuffix')} · ${caseItem.case_type}`,
        badge: t('enum.ready_for_evidence'),
        tone: 'warning',
      })),
      ...latestCases.value.slice(0, 4).map((caseItem) => ({
        id: `case-${caseItem.id}`,
        title: caseItem.case_name,
        meta: `${labelValue(caseItem.priority)}${t('dashboard.prioritySuffix')} · ${caseItem.owner || t('dashboard.unassigned')}`,
        badge: labelValue(caseItem.status),
        tone: caseItem.status === 'closed' ? 'neutral' : 'good',
      })),
    ].slice(0, 5),
  },
  {
    key: 'delivery',
    title: t('dashboard.delivery'),
    subtitle: t('dashboard.deliverySubtitle'),
    to: '/evidence',
    empty: t('dashboard.noDeliveryMaterials'),
    items: [
      ...latestEvidencePackets.value.slice(0, 5).map((packet) => ({
        id: `packet-${packet.id}`,
        title: packet.packet_name,
        meta: packet.storage_uri || packet.case_id,
        badge: t('dashboard.evidencePacks'),
        tone: 'good',
      })),
    ],
  },
])

function orderBreakdown(source: Record<string, number> | undefined, order: string[]) {
  const rows = order.map((key) => ({ label: key, value: source?.[key] ?? 0 }))
  const extras = Object.entries(source ?? {})
    .filter(([key]) => !order.includes(key))
    .map(([key, value]) => ({ label: key, value }))
  return [...rows, ...extras].filter((row) => row.value > 0)
}

function toChartRows(rows: Array<{ label: string; value: number }>) {
  return rows.map((row) => ({
    label: labelValue(row.label),
    value: row.value,
    tone: row.label,
  }))
}

function sumRows(rows: Array<{ value: number }>) {
  return rows.reduce((total, row) => total + row.value, 0)
}

function chartColor(tone: string) {
  const palette: Record<string, string> = {
    critical: '#dc2626',
    high: '#f97316',
    medium: '#f59e0b',
    low: '#14b8a6',
    new: '#2563eb',
    reviewing: '#f59e0b',
    confirmed: '#10b981',
    dismissed: '#94a3b8',
    open: '#2563eb',
    investigating: '#f97316',
    ready_for_evidence: '#8b5cf6',
    closed: '#64748b',
    tasks: '#2563eb',
    datasets: '#14b8a6',
    signals: '#f97316',
    entities: '#10b981',
    cases: '#dc2626',
    evidence: '#8b5cf6',
  }
  return palette[tone] ?? '#475569'
}

function percentage(value: number, total: number) {
  if (!total) return 0
  return Math.round((value / total) * 100)
}

function barStyle(tone: string, value: number, total: number) {
  const width = value > 0 ? Math.max(percentage(value, total), 4) : 0
  return {
    width: `${width}%`,
    background: chartColor(tone),
  }
}

function columnStyle(tone: string, value: number, total: number) {
  const height = value > 0 ? Math.max(percentage(value, total), 8) : 2
  return {
    height: `${height}%`,
    background: chartColor(tone),
  }
}

function donutStyle(rows: Array<{ tone: string; value: number }>, total: number) {
  if (!total) {
    return { background: 'conic-gradient(#e2e8f0 0 100%)' }
  }

  let cursor = 0
  const segments = rows
    .filter((row) => row.value > 0)
    .map((row) => {
      const start = (cursor / total) * 100
      cursor += row.value
      const end = (cursor / total) * 100
      return `${chartColor(row.tone)} ${start}% ${end}%`
    })

  return { background: `conic-gradient(${segments.join(', ')})` }
}

function scenarioLabel(value: string) {
  const key = `scenario.${value}`
  const translated = t(key)
  return translated === key ? value : translated
}

function labelValue(value: string) {
  const key = `enum.${value}`
  const translated = t(key)
  return translated === key ? value : translated
}
</script>

<template>
  <section class="page-grid">
    <div v-if="isLoading" class="surface section-card muted">{{ t('dashboard.loadingOverview') }}</div>
    <div v-else-if="error" class="surface section-card error-text">{{ error }}</div>

    <section class="home-hero surface">
      <div class="home-copy">
        <span class="eyebrow">{{ t('dashboard.eyebrow') }}</span>
        <h2>{{ t('dashboard.heroTitle') }}</h2>
        <p>{{ t('dashboard.heroDescription') }}</p>
      </div>
      <div class="health-grid">
        <article v-for="item in healthCards" :key="item.label" class="health-card" :class="item.tone">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
          <p>{{ item.hint }}</p>
        </article>
      </div>
    </section>

    <section class="analytics-board">
      <div class="analytics-head">
        <span class="eyebrow">{{ t('dashboard.biEyebrow') }}</span>
        <h2>{{ t('dashboard.biTitle') }}</h2>
        <p>{{ t('dashboard.biDescription') }}</p>
      </div>

      <div class="surface kpi-strip">
        <article v-for="stat in stats" :key="stat.label" class="kpi-cell">
          <span>{{ stat.label }}</span>
          <strong>{{ stat.value }}</strong>
          <small>{{ stat.hint }}</small>
          <i :style="{ background: chartColor(stat.tone) }" />
        </article>
      </div>

      <div class="analytics-grid">
        <section class="surface section-card chart-panel">
          <div class="section-head compact">
            <div>
              <h2>{{ t('dashboard.riskSignals') }}</h2>
              <p>{{ t('dashboard.signalDistribution', { count: data?.summary.signal_count ?? 0 }) }}</p>
            </div>
          </div>
          <div class="donut-layout">
            <div class="donut-chart" :style="signalRiskDonutStyle">
              <div>
                <strong>{{ signalRiskTotal }}</strong>
                <span>{{ t('dashboard.signals') }}</span>
              </div>
            </div>
            <div class="chart-list">
              <article v-for="row in signalRiskChartRows" :key="row.tone" class="chart-row">
                <div class="chart-row-label">
                  <i :style="{ background: chartColor(row.tone) }" />
                  <span>{{ row.label }}</span>
                  <strong>{{ row.value }}</strong>
                </div>
                <div class="bar-track">
                  <span :style="barStyle(row.tone, row.value, signalRiskTotal)" />
                </div>
              </article>
              <div v-if="!signalRiskChartRows.length" class="muted">{{ t('dashboard.noChartData') }}</div>
            </div>
          </div>
          <div class="subchart">
            <h3>{{ t('dashboard.signalStatusChart') }}</h3>
            <article v-for="row in signalStatusChartRows" :key="row.tone" class="chart-row compact-row">
              <div class="chart-row-label">
                <i :style="{ background: chartColor(row.tone) }" />
                <span>{{ row.label }}</span>
                <strong>{{ row.value }}</strong>
              </div>
              <div class="bar-track">
                <span :style="barStyle(row.tone, row.value, signalStatusTotal)" />
              </div>
            </article>
            <div v-if="!signalStatusChartRows.length" class="muted">{{ t('dashboard.noReviewQueue') }}</div>
          </div>
        </section>

        <section class="surface section-card chart-panel">
          <div class="section-head compact">
            <div>
              <h2>{{ t('dashboard.cases') }}</h2>
              <p>{{ t('dashboard.caseFollowing', { count: data?.summary.open_case_count ?? 0 }) }}</p>
            </div>
          </div>
          <div class="dual-chart">
            <div>
              <h3>{{ t('dashboard.caseStatusChart') }}</h3>
              <article v-for="row in caseStatusChartRows" :key="row.tone" class="chart-row">
                <div class="chart-row-label">
                  <i :style="{ background: chartColor(row.tone) }" />
                  <span>{{ row.label }}</span>
                  <strong>{{ row.value }}</strong>
                </div>
                <div class="bar-track">
                  <span :style="barStyle(row.tone, row.value, caseStatusTotal)" />
                </div>
              </article>
              <div v-if="!caseStatusChartRows.length" class="muted">{{ t('dashboard.noCaseUpdates') }}</div>
            </div>
            <div>
              <h3>{{ t('dashboard.casePriorityChart') }}</h3>
              <article v-for="row in casePriorityChartRows" :key="row.tone" class="chart-row">
                <div class="chart-row-label">
                  <i :style="{ background: chartColor(row.tone) }" />
                  <span>{{ row.label }}</span>
                  <strong>{{ row.value }}</strong>
                </div>
                <div class="bar-track">
                  <span :style="barStyle(row.tone, row.value, casePriorityTotal)" />
                </div>
              </article>
              <div v-if="!casePriorityChartRows.length" class="muted">{{ t('dashboard.noCases') }}</div>
            </div>
          </div>
        </section>

        <section class="surface section-card chart-panel">
          <div class="section-head compact">
            <div>
              <h2>{{ t('dashboard.pipelineChart') }}</h2>
              <p>{{ t('dashboard.operationOverviewDescription') }}</p>
            </div>
          </div>
          <div class="pipeline-chart">
            <article v-for="row in pipelineRows" :key="row.tone" class="pipeline-stage">
              <div class="stage-rail">
                <span :style="columnStyle(row.tone, row.value, pipelineMax)" />
              </div>
              <strong>{{ row.value }}</strong>
              <small>{{ row.label }}</small>
            </article>
          </div>
        </section>

        <section class="surface section-card chart-panel">
          <div class="section-head compact">
            <div>
              <h2>{{ t('dashboard.riskConcentration') }}</h2>
              <p>{{ t('dashboard.platformRiskDescription') }}</p>
            </div>
          </div>
          <div class="leaderboard-groups">
            <div>
              <h3>{{ t('dashboard.platformRisk') }}</h3>
              <article v-for="row in topPlatformRiskRows" :key="row.key" class="leader-row">
                <div>
                  <strong>{{ row.key }}</strong>
                  <span>{{ t('dashboard.signals') }} {{ row.signal_count }} · {{ t('dashboard.datasets') }} {{ row.dataset_count }}</span>
                </div>
                <small>{{ row.high_risk_signal_count }}</small>
                <div class="bar-track">
                  <span :style="barStyle('high', row.high_risk_signal_count, platformRiskMax)" />
                </div>
              </article>
              <div v-if="!topPlatformRiskRows.length" class="muted">{{ t('dashboard.noPlatformRiskData') }}</div>
            </div>
            <div>
              <h3>{{ t('dashboard.scenarioRisk') }}</h3>
              <article v-for="row in topScenarioRiskRows" :key="row.key" class="leader-row">
                <div>
                  <strong>{{ scenarioLabel(row.key) }}</strong>
                  <span>{{ t('dashboard.signals') }} {{ row.signal_count }} · {{ t('dashboard.cases') }} {{ row.case_count }}</span>
                </div>
                <small>{{ row.high_risk_signal_count }}</small>
                <div class="bar-track">
                  <span :style="barStyle('cases', row.high_risk_signal_count, scenarioRiskMax)" />
                </div>
              </article>
              <div v-if="!topScenarioRiskRows.length" class="muted">{{ t('dashboard.noScenarioRiskData') }}</div>
            </div>
          </div>
        </section>
      </div>
    </section>

    <section class="surface section-card">
      <div class="section-head board-head">
        <div>
          <h2>{{ t('dashboard.workBoard') }}</h2>
          <p>{{ t('dashboard.workBoardDescription') }}</p>
        </div>
      </div>
      <div class="kanban-grid">
        <section v-for="column in boardColumns" :key="column.key" class="kanban-column">
          <div class="kanban-column-head">
            <div>
              <h3>{{ column.title }}</h3>
              <p>{{ column.subtitle }}</p>
            </div>
            <RouterLink :to="column.to" class="column-link">{{ t('dashboard.enter') }}</RouterLink>
          </div>
          <div class="kanban-list">
            <article v-for="item in column.items" :key="item.id" class="kanban-card" :class="item.tone">
              <div>
                <strong>{{ item.title }}</strong>
                <span>{{ item.meta }}</span>
              </div>
              <small>{{ item.badge }}</small>
            </article>
            <div v-if="!column.items.length" class="kanban-empty">{{ column.empty }}</div>
          </div>
        </section>
      </div>
    </section>

    <div class="overview-grid">
      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>{{ t('dashboard.pendingSignalTitle') }}</h2>
            <p>{{ t('dashboard.pendingSignalDescription') }}</p>
          </div>
        </div>
        <div class="compact-list">
          <article v-for="item in pendingSignals" :key="item.id" class="compact-item">
            <strong>{{ item.summary }}</strong>
            <span>{{ labelValue(item.risk_level) }} · {{ labelValue(item.status) }} · {{ t('dashboard.score', { score: item.risk_score }) }}</span>
          </article>
          <div v-if="!pendingSignals.length" class="muted">{{ t('dashboard.noHighRiskReviewQueue') }}</div>
        </div>
      </section>

      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>{{ t('dashboard.readyEvidence') }}</h2>
            <p>{{ t('dashboard.readyEvidenceDescription') }}</p>
          </div>
        </div>
        <div class="compact-list">
          <article v-for="item in readyCases" :key="item.id" class="compact-item">
            <strong>{{ item.case_name }}</strong>
            <span>{{ labelValue(item.priority) }} · {{ labelValue(item.status) }} · {{ item.case_type }}</span>
          </article>
          <div v-if="!readyCases.length" class="muted">{{ t('dashboard.noReadyEvidenceCases') }}</div>
        </div>
      </section>
    </div>

    <div class="overview-grid">
      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>{{ t('dashboard.failedRuns') }}</h2>
            <p>{{ t('dashboard.failedRunsDescription') }}</p>
          </div>
        </div>
        <div class="compact-list">
          <article v-for="item in failedRuns" :key="item.id" class="compact-item">
            <strong>{{ item.task_id }}</strong>
            <span>{{ item.status }} · {{ item.error_message || item.finished_at || '-' }}</span>
          </article>
          <div v-if="!failedRuns.length" class="muted">{{ t('dashboard.noFailedRuns') }}</div>
        </div>
      </section>

      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>{{ t('dashboard.operationOverview') }}</h2>
            <p>{{ t('dashboard.operationOverviewDescription') }}</p>
          </div>
        </div>
        <div class="mini-grid">
          <article v-for="item in operationalStats" :key="item.label" class="mini-stat">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </article>
        </div>
      </section>

      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>{{ t('dashboard.platformCoverage') }}</h2>
            <p>{{ t('dashboard.platformCoverageDescription', { count: platformItems.length }) }}</p>
          </div>
        </div>
        <div v-if="platformsLoading" class="muted">{{ t('dashboard.loadingPlatforms') }}</div>
        <div v-else-if="platformsError" class="muted">{{ platformsError }}</div>
        <div v-else class="chip-grid">
          <article v-for="item in platformItems" :key="item.platform" class="chip-card">
            <strong>{{ item.label }}</strong>
            <span>
              {{ t('dashboard.extractorCount', { count: item.supported_signal_extractors.length }) }}
              ·
              {{ t('dashboard.analysisTypeCount', { count: item.supported_analysis_types.length }) }}
            </span>
          </article>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.page-grid {
  display: grid;
  gap: 16px;
}

.home-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(470px, 0.9fr);
  gap: 20px;
  align-items: stretch;
  overflow: hidden;
  border-radius: var(--radius);
  padding: 24px;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(241, 248, 250, 0.88)),
    var(--card);
}

.home-copy {
  display: grid;
  align-content: center;
  gap: 12px;
}

.home-copy h2 {
  margin: 0;
  max-width: 760px;
  font-size: 30px;
  line-height: 1.18;
}

.home-copy p {
  margin: 0;
  max-width: 760px;
  color: #64748b;
  line-height: 1.7;
}

.health-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.health-card {
  min-height: 134px;
  padding: 15px;
  border-radius: var(--radius);
  border: 1px solid rgba(215, 224, 234, 0.86);
  background: rgba(248, 250, 252, 0.88);
}

.health-card span,
.health-card p {
  color: #64748b;
}

.health-card span {
  display: block;
  margin-bottom: 10px;
  font-size: 12px;
  font-weight: 800;
}

.health-card strong {
  display: block;
  margin-bottom: 8px;
  font-size: 21px;
  line-height: 1.22;
  word-break: keep-all;
}

.health-card p {
  margin: 0;
  line-height: 1.5;
}

.health-card.good {
  border-color: rgba(16, 185, 129, 0.28);
  background: rgba(236, 253, 245, 0.72);
}

.health-card.warning {
  border-color: rgba(245, 158, 11, 0.3);
  background: rgba(255, 251, 235, 0.78);
}

.health-card.danger {
  border-color: rgba(239, 68, 68, 0.3);
  background: rgba(254, 242, 242, 0.78);
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.section-card {
  overflow: hidden;
  border-radius: var(--radius);
  padding: 20px;
}

.eyebrow {
  display: block;
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0;
  text-transform: uppercase;
  color: #64748b;
}

.section-head p,
.muted,
.compact-item span,
.chip-card span {
  color: #64748b;
}

.section-head {
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid rgba(215, 224, 234, 0.7);
}

.board-head {
  margin-bottom: 18px;
}

.section-head h2 {
  margin: 0 0 6px;
}

.section-head.compact {
  margin-bottom: 16px;
  padding-bottom: 12px;
}

.analytics-board {
  display: grid;
  gap: 14px;
}

.analytics-head {
  display: grid;
  gap: 6px;
  padding: 2px 2px 0;
}

.analytics-head h2 {
  margin: 0;
  font-size: 23px;
}

.analytics-head p {
  max-width: 760px;
  margin: 0;
  color: #64748b;
  line-height: 1.6;
}

.kpi-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  overflow: hidden;
  border-radius: var(--radius);
}

.kpi-cell {
  position: relative;
  min-height: 116px;
  padding: 18px 20px 16px;
  display: grid;
  align-content: space-between;
  gap: 10px;
  border-right: 1px solid rgba(215, 224, 234, 0.72);
}

.kpi-cell:last-child {
  border-right: 0;
}

.kpi-cell span,
.kpi-cell small {
  color: #64748b;
}

.kpi-cell span {
  font-size: 12px;
  font-weight: 800;
}

.kpi-cell strong {
  font-size: 38px;
  line-height: 0.95;
}

.kpi-cell i {
  position: absolute;
  inset: auto 16px 14px auto;
  width: 48px;
  height: 4px;
  border-radius: 999px;
  opacity: 0.9;
}

.analytics-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(0, 0.92fr);
  gap: 16px;
}

.chart-panel {
  min-height: 356px;
  display: grid;
  align-content: start;
  gap: 16px;
}

.donut-layout {
  display: grid;
  grid-template-columns: 186px minmax(0, 1fr);
  gap: 18px;
  align-items: center;
}

.donut-chart {
  width: 178px;
  aspect-ratio: 1;
  padding: 20px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  box-shadow: 0 18px 34px rgba(15, 23, 42, 0.08);
}

.donut-chart > div {
  width: 112px;
  aspect-ratio: 1;
  border-radius: 50%;
  display: grid;
  place-items: center;
  align-content: center;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: inset 0 0 0 1px rgba(215, 224, 234, 0.86);
}

.donut-chart strong,
.donut-chart span {
  display: block;
  text-align: center;
}

.donut-chart strong {
  font-size: 30px;
  line-height: 1;
}

.donut-chart span {
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.chart-list,
.subchart,
.dual-chart,
.leaderboard-groups {
  display: grid;
  gap: 12px;
}

.subchart {
  padding-top: 14px;
  border-top: 1px solid rgba(215, 224, 234, 0.7);
}

.dual-chart {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: start;
}

.subchart h3,
.dual-chart h3,
.leaderboard-groups h3 {
  margin: 0 0 10px;
  color: #334155;
  font-size: 13px;
  font-weight: 900;
}

.chart-row {
  display: grid;
  gap: 8px;
}

.chart-row.compact-row {
  gap: 7px;
}

.chart-row-label {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr) auto;
  gap: 9px;
  align-items: center;
}

.chart-row-label i {
  width: 10px;
  height: 10px;
  border-radius: 999px;
}

.chart-row-label span,
.leader-row span {
  min-width: 0;
  color: #64748b;
  overflow-wrap: anywhere;
}

.chart-row-label strong,
.leader-row small {
  color: #0f172a;
  font-weight: 900;
}

.bar-track {
  height: 9px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(226, 232, 240, 0.82);
}

.bar-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
}

.pipeline-chart {
  min-height: 248px;
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
  align-items: end;
}

.pipeline-stage {
  min-width: 0;
  display: grid;
  gap: 8px;
  align-items: end;
  text-align: center;
}

.stage-rail {
  height: 168px;
  padding: 5px;
  border-radius: var(--radius);
  display: flex;
  align-items: end;
  background:
    linear-gradient(180deg, rgba(226, 232, 240, 0.28), rgba(226, 232, 240, 0.76)),
    repeating-linear-gradient(180deg, transparent 0 23px, rgba(148, 163, 184, 0.18) 23px 24px);
}

.stage-rail span {
  width: 100%;
  border-radius: 5px;
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.12);
}

.pipeline-stage strong {
  font-size: 20px;
}

.pipeline-stage small {
  min-height: 32px;
  color: #64748b;
  font-weight: 800;
  overflow-wrap: anywhere;
}

.leaderboard-groups {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.leader-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 9px 12px;
  align-items: center;
  padding: 11px 0;
  border-bottom: 1px solid rgba(215, 224, 234, 0.7);
}

.leader-row:last-of-type {
  border-bottom: 0;
}

.leader-row strong,
.leader-row span {
  display: block;
}

.leader-row strong {
  margin-bottom: 4px;
  overflow-wrap: anywhere;
}

.leader-row .bar-track {
  grid-column: 1 / -1;
}

.kanban-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.kanban-column {
  min-width: 0;
  display: grid;
  align-content: start;
  gap: 12px;
  padding: 14px;
  border-radius: var(--radius);
  border: 1px solid rgba(215, 224, 234, 0.84);
  background: rgba(248, 250, 252, 0.72);
}

.kanban-column-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.kanban-column-head h3 {
  margin: 0 0 6px;
  font-size: 16px;
}

.kanban-column-head p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
  line-height: 1.5;
}

.column-link {
  flex-shrink: 0;
  color: var(--primary);
  font-size: 13px;
  font-weight: 800;
  text-decoration: none;
}

.kanban-list {
  display: grid;
  gap: 10px;
}

.kanban-card {
  display: grid;
  gap: 10px;
  min-height: 108px;
  padding: 14px;
  border-radius: var(--radius);
  border: 1px solid rgba(215, 224, 234, 0.86);
  background: #fff;
}

.kanban-card strong,
.kanban-card span {
  display: block;
  min-width: 0;
  overflow-wrap: anywhere;
}

.kanban-card strong {
  margin-bottom: 6px;
}

.kanban-card span {
  color: #64748b;
  font-size: 13px;
  line-height: 1.5;
}

.kanban-card small {
  width: fit-content;
  padding: 6px 9px;
  border-radius: var(--radius);
  background: color-mix(in oklch, var(--primary) 10%, white);
  color: var(--primary);
  font-weight: 800;
}

.kanban-card.good small {
  background: rgba(16, 185, 129, 0.12);
  color: #047857;
}

.kanban-card.warning small {
  background: rgba(245, 158, 11, 0.14);
  color: #b45309;
}

.kanban-card.danger small {
  background: rgba(239, 68, 68, 0.12);
  color: #b91c1c;
}

.kanban-empty {
  padding: 18px 14px;
  border-radius: var(--radius);
  border: 1px dashed rgba(148, 163, 184, 0.55);
  color: #64748b;
  background: rgba(255, 255, 255, 0.72);
}

.chip-grid,
.compact-list,
.meter-list,
.risk-table {
  display: grid;
  gap: 12px;
}

.chip-card,
.compact-item,
.meter-row,
.mini-stat {
  padding: 14px 16px;
  border-radius: var(--radius);
  border: 1px solid rgba(215, 224, 234, 0.84);
  background: rgba(248, 250, 252, 0.84);
}

.chip-card strong,
.compact-item strong {
  display: block;
  margin-bottom: 6px;
}

.breakdown-grid,
.mini-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.breakdown-grid h3 {
  margin: 0 0 10px;
  font-size: 14px;
}

.meter-row,
.mini-stat {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.meter-row span,
.mini-stat span {
  color: #64748b;
  text-transform: capitalize;
}

.risk-head,
.risk-row {
  display: grid;
  grid-template-columns: minmax(120px, 1.6fr) repeat(4, minmax(56px, 0.7fr));
  gap: 10px;
  align-items: center;
}

.risk-head {
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.risk-row {
  padding: 12px 14px;
  border-radius: var(--radius);
  border: 1px solid rgba(215, 224, 234, 0.84);
  background: rgba(248, 250, 252, 0.84);
}

.risk-row strong,
.risk-row span {
  min-width: 0;
  overflow-wrap: anywhere;
}

.risk-row span {
  color: #334155;
  font-weight: 700;
}

.error-text {
  color: #dc2626;
}

@media (max-width: 1280px) {
  .home-hero,
  .kanban-grid,
  .analytics-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .kpi-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .kpi-cell:nth-child(2) {
    border-right: 0;
  }

  .kpi-cell:nth-child(-n + 2) {
    border-bottom: 1px solid rgba(215, 224, 234, 0.72);
  }
}

@media (max-width: 920px) {
  .home-hero,
  .health-grid,
  .kpi-strip,
  .analytics-grid,
  .donut-layout,
  .dual-chart,
  .leaderboard-groups,
  .kanban-grid,
  .overview-grid,
  .breakdown-grid,
  .mini-grid,
  .risk-head,
  .risk-row {
    grid-template-columns: 1fr;
  }

  .kpi-cell {
    border-right: 0;
    border-bottom: 1px solid rgba(215, 224, 234, 0.72);
  }

  .kpi-cell:last-child {
    border-bottom: 0;
  }

  .donut-chart {
    justify-self: center;
  }

  .pipeline-chart {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
</style>
