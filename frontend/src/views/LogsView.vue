<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getRunLog, listRunLogs } from '../api/logs'
import type { RunLogDetail, RunLogEntry } from '../types'

const entries = ref<RunLogEntry[]>([])
const selected = ref<RunLogDetail | null>(null)
const isLoading = ref(false)
const isLoadingLog = ref(false)
const error = ref('')
const logError = ref('')

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
    logError.value = 'This run has no readable log.'
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

onMounted(fetchEntries)
</script>

<template>
  <section class="page-grid">
    <section class="surface section-card">
      <div class="section-head">
        <div>
          <h2>Run Logs</h2>
          <p>任务运行日志、退出状态和数据集物化结果集中在这里审计。</p>
        </div>
        <button class="secondary-button" type="button" @click="fetchEntries">Refresh</button>
      </div>

      <div class="stats-grid">
        <div class="stat-item">
          <span>Total Runs</span>
          <strong>{{ entries.length }}</strong>
        </div>
        <div class="stat-item">
          <span>Succeeded</span>
          <strong>{{ successfulRuns }}</strong>
        </div>
        <div class="stat-item">
          <span>Failed</span>
          <strong>{{ failedRuns }}</strong>
        </div>
        <div class="stat-item">
          <span>Logs</span>
          <strong>{{ runsWithLogs }}</strong>
        </div>
      </div>
    </section>

    <section class="content-grid">
      <section class="surface section-card">
        <div class="section-head compact">
          <div>
            <h2>Run History</h2>
            <p>最近的采集运行记录。</p>
          </div>
        </div>

        <div v-if="isLoading" class="muted">Loading logs...</div>
        <div v-else-if="error" class="error-text">{{ error }}</div>
        <div v-else class="run-list">
          <button
            v-for="entry in entries"
            :key="entry.run.id"
            class="run-item"
            type="button"
            @click="selectRun(entry)"
          >
            <span class="status-badge">{{ entry.run.status }}</span>
            <strong>{{ entry.run.task_id }}</strong>
            <span>{{ entry.run.started_at || '-' }}</span>
            <span>{{ entry.has_log ? formatBytes(entry.log_size) : 'no log' }}</span>
          </button>
          <div v-if="!entries.length" class="muted">No task runs yet.</div>
        </div>
      </section>

      <section class="surface section-card log-card">
        <div class="section-head compact">
          <div>
            <h2>Log Output</h2>
            <p v-if="selected">{{ selected.run.id }} · {{ selected.line_count }} lines</p>
            <p v-else>选择一条运行记录查看日志。</p>
          </div>
        </div>

        <div v-if="isLoadingLog" class="muted">Loading log...</div>
        <div v-else-if="logError" class="error-text">{{ logError }}</div>
        <pre v-else-if="selected" class="log-output">{{ selected.content }}</pre>
        <div v-else class="muted">No log selected.</div>
      </section>
    </section>
  </section>
</template>

<style scoped>
.page-grid,
.run-list {
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
  grid-template-columns: repeat(4, minmax(0, 1fr));
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

.content-grid {
  display: grid;
  grid-template-columns: minmax(280px, 0.9fr) minmax(0, 1.4fr);
  gap: 16px;
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
  .content-grid {
    grid-template-columns: 1fr;
  }

  .section-head {
    display: grid;
  }
}
</style>
