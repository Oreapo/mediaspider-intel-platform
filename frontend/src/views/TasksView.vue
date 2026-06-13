<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  createTask,
  disableTask,
  enableTask,
  getCrawlerDiagnostics,
  getSchedulerStatus,
  listTaskRuns,
  runScheduledTasks,
  startTaskRun,
} from '../api/tasks'
import AppAlert from '../components/ui/AppAlert.vue'
import BaseSection from '../components/ui/BaseSection.vue'
import EmptyState from '../components/ui/EmptyState.vue'
import FieldError from '../components/ui/FieldError.vue'
import LoadingState from '../components/ui/LoadingState.vue'
import PaginationBar from '../components/ui/PaginationBar.vue'
import PermissionGate from '../components/ui/PermissionGate.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import { useI18n } from '../composables/useI18n'
import { usePlatformModels } from '../composables/usePlatformModels'
import { useTasks } from '../composables/useTasks'
import { lastPageOffset } from '../lib/pagination'
import { nonNegativeNumber, required, type ValidationErrors } from '../lib/validation'
import type { CrawlerDiagnostics, PlatformTaskModel, SchedulerStatus, TaskRun } from '../types'

const { items: platformItems } = usePlatformModels()
const { t } = useI18n()
const {
  items: taskItems,
  total: taskTotal,
  isLoading: tasksLoading,
  error: tasksError,
  fetchItems: fetchTasks,
} = useTasks()

const form = ref({
  task_name: '',
  platform: 'xhs',
  entity_type: 'content',
  task_mode: 'search',
  scenario_type: 'lead_diversion',
  primary_input: '',
  notes: '',
  start_page: 1,
  enable_comments: true,
  enable_sub_comments: false,
  headless: false,
  analysis_types: 'summary,keywords',
})
const filters = ref({
  q: '',
  platform: '',
  status: '',
  task_mode: '',
  entity_type: '',
  scenario_type: '',
  limit: 100,
  offset: 0,
})
const submitting = ref(false)
const submitError = ref('')
const submitMessage = ref('')
const formErrors = ref<ValidationErrors>({})
const actionMessage = ref('')
const actionError = ref('')
const runsByTask = ref<Record<string, TaskRun[]>>({})
const diagnosticsByTask = ref<Record<string, CrawlerDiagnostics>>({})
const runningTaskIds = ref<string[]>([])
const diagnosingTaskIds = ref<string[]>([])
const schedulerBusy = ref(false)
const schedulerResult = ref<Record<string, unknown> | null>(null)
const schedulerStatus = ref<SchedulerStatus | null>(null)
const schedulerStatusError = ref('')

const scenarioOptions = computed(() => [
  { value: 'lead_diversion', label: t('scenario.lead_diversion') },
  { value: 'gray_recruitment', label: t('scenario.gray_recruitment') },
  { value: 'fraud_promotion', label: t('scenario.fraud_promotion') },
  { value: 'seller_risk', label: t('scenario.seller_risk') },
  { value: 'product_risk', label: t('scenario.product_risk') },
  { value: 'topic_watch', label: t('scenario.topic_watch') },
])

const selectedModel = computed<PlatformTaskModel | undefined>(() =>
  platformItems.value.find((item) => item.platform === form.value.platform),
)

const visibleFieldHints = computed(() => {
  const model = selectedModel.value
  if (!model) return []
  return model.task_fields.filter((field) => {
    if (field.group !== 'filters' && field.group !== 'runtime' && field.group !== 'analysis') {
      return false
    }
    return !field.visible_for_modes.length || field.visible_for_modes.includes(form.value.task_mode)
  })
})

const taskModes = computed(() => Array.from(new Set(taskItems.value.map((item) => item.task_mode))).sort())
const entityTypes = computed(() => Array.from(new Set(taskItems.value.map((item) => item.entity_type))).sort())

watch(
  selectedModel,
  (model) => {
    if (!model) return
    if (!model.supported_entity_types.includes(form.value.entity_type)) {
      form.value.entity_type = model.supported_entity_types[0] || 'content'
    }
    if (!model.supported_modes.includes(form.value.task_mode)) {
      form.value.task_mode = model.supported_modes[0] || 'search'
    }
  },
  { immediate: true },
)

watch(
  taskItems,
  async (items) => {
    const entries = await Promise.all(
      items.map(async (item) => {
        try {
          return [item.id, await listTaskRuns(item.id)] as const
        } catch {
          return [item.id, []] as const
        }
      }),
    )
    runsByTask.value = Object.fromEntries(entries)
  },
  { deep: true },
)

const inputLabel = computed(() => {
  if (form.value.task_mode === 'detail') return t('tasks.detailInput')
  if (form.value.task_mode === 'creator') return t('tasks.creatorInput')
  return t('tasks.keywordInput')
})

const inputPlaceholder = computed(() => {
  if (form.value.task_mode === 'detail') return t('tasks.detailPlaceholder')
  if (form.value.task_mode === 'creator') return t('tasks.creatorPlaceholder')
  return t('tasks.keywordPlaceholder')
})

function toStringList(text: string) {
  return text
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function validateTaskForm() {
  const errors: ValidationErrors = {}
  const nameError = required(form.value.task_name, t('tasks.taskName'))
  const inputError = required(form.value.primary_input, inputLabel.value)
  const startPageError = nonNegativeNumber(form.value.start_page - 1, t('tasks.startPage'))

  if (nameError) errors.task_name = nameError
  if (inputError) errors.primary_input = inputError
  if (startPageError) errors.start_page = t('tasks.startPageInvalid')
  if (!toStringList(form.value.analysis_types).length) errors.analysis_types = t('tasks.analysisTypesRequired')

  formErrors.value = errors
  return Object.keys(errors).length === 0
}

async function submitTask() {
  submitError.value = ''
  submitMessage.value = ''
  if (!validateTaskForm()) {
    submitError.value = t('tasks.fixFormErrors')
    return
  }

  submitting.value = true
  try {
    const list = toStringList(form.value.primary_input)
    const taskPayload: Record<string, unknown> = {}
    if (form.value.task_mode === 'search') taskPayload.keywords = list
    if (form.value.task_mode === 'detail') taskPayload.specified_ids = list
    if (form.value.task_mode === 'creator') taskPayload.creator_ids = list

    await createTask({
      task_name: form.value.task_name,
      platform: form.value.platform,
      entity_type: form.value.entity_type,
      task_mode: form.value.task_mode,
      scenario_type: form.value.scenario_type,
      task_payload_json: taskPayload,
      runtime_payload_json: {
        start_page: form.value.start_page,
        enable_comments: form.value.enable_comments,
        enable_sub_comments: form.value.enable_sub_comments,
        headless: form.value.headless,
      },
      analysis_profile_json: {
        analysis_types: toStringList(form.value.analysis_types),
      },
      notes: form.value.notes,
    })
    submitMessage.value = t('tasks.createdMessage')
    form.value.task_name = ''
    form.value.primary_input = ''
    form.value.notes = ''
    await fetchTaskPage()
  } catch (err) {
    submitError.value = err instanceof Error ? err.message : String(err)
  } finally {
    submitting.value = false
  }
}

async function applyFilters() {
  filters.value.offset = 0
  await fetchTaskPage()
}

async function fetchTaskPage() {
  await fetchTasks({
    q: filters.value.q,
    platform: filters.value.platform,
    status: filters.value.status,
    task_mode: filters.value.task_mode,
    entity_type: filters.value.entity_type,
    scenario_type: filters.value.scenario_type,
    limit: filters.value.limit,
    offset: filters.value.offset,
  })
  const normalizedOffset = lastPageOffset(taskTotal.value, filters.value.limit)
  if (filters.value.offset > normalizedOffset) {
    filters.value.offset = normalizedOffset
    if (taskTotal.value > 0) await fetchTaskPage()
  }
}

async function changeTaskPage(offset: number) {
  filters.value.offset = offset
  await fetchTaskPage()
}

async function clearFilters() {
  filters.value = {
    q: '',
    platform: '',
    status: '',
    task_mode: '',
    entity_type: '',
    scenario_type: '',
    limit: 100,
    offset: 0,
  }
  await applyFilters()
}

async function runAction(type: 'enable' | 'disable' | 'run', taskId: string) {
  actionError.value = ''
  actionMessage.value = ''
  try {
    if (type === 'enable') await enableTask(taskId)
    if (type === 'disable') await disableTask(taskId)
    if (type === 'run') {
      runningTaskIds.value = [...runningTaskIds.value, taskId]
      const run = await startTaskRun(taskId)
      runsByTask.value = {
        ...runsByTask.value,
        [taskId]: [run, ...(runsByTask.value[taskId] || []).filter((item) => item.id !== run.id)],
      }
      actionMessage.value =
        run.status === 'succeeded'
          ? t('tasks.runCompleted')
          : t('tasks.runStatus', { status: labelValue(run.status) })
    } else {
      actionMessage.value = type === 'enable' ? t('tasks.enabledMessage') : t('tasks.disabledMessage')
    }
    await fetchTaskPage()
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : String(err)
  } finally {
    runningTaskIds.value = runningTaskIds.value.filter((id) => id !== taskId)
  }
}

async function diagnoseTask(taskId: string) {
  actionError.value = ''
  actionMessage.value = ''
  diagnosingTaskIds.value = [...diagnosingTaskIds.value, taskId]
  try {
    const diagnostics = await getCrawlerDiagnostics(taskId)
    diagnosticsByTask.value = {
      ...diagnosticsByTask.value,
      [taskId]: diagnostics,
    }
    actionMessage.value = diagnostics.ready ? t('tasks.diagnosticsReady') : t('tasks.diagnosticsBlocked')
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : String(err)
  } finally {
    diagnosingTaskIds.value = diagnosingTaskIds.value.filter((id) => id !== taskId)
  }
}

async function runScheduler() {
  actionError.value = ''
  actionMessage.value = ''
  schedulerBusy.value = true
  try {
    schedulerResult.value = await runScheduledTasks(true)
    const count = Array.isArray(schedulerResult.value.results) ? schedulerResult.value.results.length : 0
    actionMessage.value = t('tasks.schedulerRunDone', { count })
    await fetchTaskPage()
    await loadSchedulerStatus()
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : String(err)
  } finally {
    schedulerBusy.value = false
  }
}

async function dryRunScheduler() {
  actionError.value = ''
  actionMessage.value = ''
  schedulerBusy.value = true
  try {
    schedulerResult.value = await runScheduledTasks(false)
    const count = Array.isArray(schedulerResult.value.results) ? schedulerResult.value.results.length : 0
    actionMessage.value = t('tasks.schedulerDryRunDone', { count })
    await fetchTaskPage()
    await loadSchedulerStatus()
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : String(err)
  } finally {
    schedulerBusy.value = false
  }
}

async function loadSchedulerStatus() {
  schedulerStatusError.value = ''
  try {
    schedulerStatus.value = await getSchedulerStatus()
  } catch (err) {
    schedulerStatusError.value = err instanceof Error ? err.message : String(err)
  }
}

const latestSchedulerHistory = computed(() => schedulerStatus.value?.run_history?.slice(0, 5) || [])

function latestRuns(taskId: string) {
  return (runsByTask.value[taskId] || []).slice(0, 3)
}

function diagnosticCommand(taskId: string) {
  return diagnosticsByTask.value[taskId]?.command.join(' ') || ''
}

function statusTone(status: string) {
  if (['enabled', 'succeeded', 'ready'].includes(status)) return 'success'
  if (['running', 'draft'].includes(status)) return 'info'
  if (['disabled', 'skipped'].includes(status)) return 'neutral'
  if (['failed', 'blocked'].includes(status)) return 'danger'
  return 'neutral'
}

function schedulerResultCount(item: { results?: Array<Record<string, unknown>> }) {
  return Array.isArray(item.results) ? item.results.length : 0
}

function schedulerTriggerLabel(triggerType?: string) {
  return triggerType === 'manual' ? t('tasks.schedulerManual') : t('tasks.schedulerBackground')
}

function labelValue(value: string) {
  const key = `enum.${value}`
  const translated = t(key)
  return translated === key ? value : translated
}

function scenarioLabel(value: string) {
  const key = `scenario.${value}`
  const translated = t(key)
  return translated === key ? value : translated
}

onMounted(loadSchedulerStatus)
</script>

<template>
  <section class="page-grid">
    <div class="task-workspace">
      <aside class="task-side-panel">
    <BaseSection compact :title="t('tasks.formTitle')" :description="t('tasks.formDescription')">
      <PermissionGate area="operations">
      <form class="task-form" @submit.prevent="submitTask">
        <label class="field">
          <span>{{ t('tasks.taskName') }}</span>
          <input v-model="form.task_name" required :placeholder="t('tasks.taskNamePlaceholder')" />
          <FieldError :message="formErrors.task_name" />
        </label>

        <div class="grid-two">
          <label class="field">
            <span>{{ t('tasks.platform') }}</span>
            <select v-model="form.platform">
              <option v-for="item in platformItems" :key="item.platform" :value="item.platform">
                {{ item.label }}
              </option>
            </select>
          </label>

          <label class="field">
            <span>{{ t('tasks.entityType') }}</span>
            <select v-model="form.entity_type">
              <option
                v-for="entity in selectedModel?.supported_entity_types || []"
                :key="entity"
                :value="entity"
              >
                {{ entity }}
              </option>
            </select>
          </label>
        </div>

        <div class="grid-two">
          <label class="field">
            <span>{{ t('tasks.scenario') }}</span>
            <select v-model="form.scenario_type">
              <option v-for="item in scenarioOptions" :key="item.value" :value="item.value">
                {{ item.label }}
              </option>
            </select>
          </label>

          <label class="field">
            <span>{{ t('tasks.taskMode') }}</span>
            <select v-model="form.task_mode">
              <option v-for="mode in selectedModel?.supported_modes || []" :key="mode" :value="mode">
                {{ mode }}
              </option>
            </select>
          </label>

        </div>

        <label class="field">
          <span>{{ t('tasks.startPage') }}</span>
          <input v-model.number="form.start_page" min="1" step="1" type="number" />
          <FieldError :message="formErrors.start_page" />
        </label>

        <label class="field">
          <span>{{ inputLabel }}</span>
          <textarea v-model="form.primary_input" :placeholder="inputPlaceholder" required rows="5" />
          <FieldError :message="formErrors.primary_input" />
        </label>

        <label class="field">
          <span>{{ t('tasks.analysisTypes') }}</span>
          <input v-model="form.analysis_types" placeholder="risk_terms,contact_points,template_similarity" />
          <FieldError :message="formErrors.analysis_types" />
        </label>

        <label class="field">
          <span>{{ t('tasks.notes') }}</span>
          <textarea v-model="form.notes" :placeholder="t('tasks.notesPlaceholder')" rows="3" />
        </label>

        <div class="toggle-row">
          <label><input v-model="form.enable_comments" type="checkbox" /> {{ t('tasks.enableComments') }}</label>
          <label><input v-model="form.enable_sub_comments" type="checkbox" /> {{ t('tasks.enableSubComments') }}</label>
          <label><input v-model="form.headless" type="checkbox" /> {{ t('tasks.headless') }}</label>
        </div>

        <div v-if="visibleFieldHints.length" class="hint-card">
          <strong>{{ t('tasks.platformFieldHints') }}</strong>
          <ul>
            <li v-for="field in visibleFieldHints" :key="field.key">
              {{ field.label }} · {{ field.group }} · {{ field.control }}
            </li>
          </ul>
        </div>

        <div class="actions">
          <button class="primary-button" :disabled="submitting" type="submit">
            {{ submitting ? t('tasks.creating') : t('tasks.createTask') }}
          </button>
        </div>
        <AppAlert v-if="submitMessage" tone="success" :title="t('tasks.successTitle')" :message="submitMessage" />
        <AppAlert v-if="submitError" tone="error" :title="t('tasks.createFailedTitle')" :message="submitError" />
      </form>
      </PermissionGate>
    </BaseSection>

    <BaseSection compact :title="t('tasks.schedulerTitle')" :description="t('tasks.schedulerDescription')">
      <template #actions>
        <button class="secondary-button" type="button" @click="loadSchedulerStatus">{{ t('tasks.refreshStatus') }}</button>
      </template>
      <AppAlert v-if="schedulerStatusError" tone="error" :title="t('tasks.schedulerLoadFailed')" :message="schedulerStatusError" />
      <div v-if="schedulerStatus" class="scheduler-grid">
        <article class="scheduler-card">
          <span>{{ t('tasks.runningStatus') }}</span>
          <strong>{{ schedulerStatus.is_running ? t('tasks.schedulerRunning') : t('tasks.schedulerStopped') }}</strong>
        </article>
        <article class="scheduler-card">
          <span>{{ t('tasks.scanActivity') }}</span>
          <strong>{{ schedulerStatus.is_executing ? t('tasks.schedulerExecuting') : t('tasks.schedulerIdle') }}</strong>
        </article>
        <article class="scheduler-card">
          <span>{{ t('tasks.queuedRuns') }}</span>
          <strong>{{ schedulerStatus.queued_runs }}</strong>
        </article>
        <article class="scheduler-card">
          <span>{{ t('tasks.taskRunCapacity') }}</span>
          <strong>{{ schedulerStatus.active_task_runs }} / {{ schedulerStatus.max_concurrent_task_runs }}</strong>
        </article>
        <article class="scheduler-card">
          <span>{{ t('tasks.taskRunQueue') }}</span>
          <strong>{{ schedulerStatus.queued_task_runs }}</strong>
        </article>
        <article class="scheduler-card">
          <span>{{ t('tasks.taskQueueTimeout') }}</span>
          <strong>{{ schedulerStatus.task_queue_timeout_seconds }}s</strong>
        </article>
        <article class="scheduler-card">
          <span>{{ t('tasks.recoveredRuns') }}</span>
          <strong>{{ schedulerStatus.recovered_task_runs }}</strong>
        </article>
        <article class="scheduler-card">
          <span>{{ t('tasks.scanInterval') }}</span>
          <strong>{{ schedulerStatus.interval_seconds }}s</strong>
        </article>
        <article class="scheduler-card">
          <span>{{ t('tasks.runTimeout') }}</span>
          <strong>{{ schedulerStatus.run_timeout_seconds }}s</strong>
        </article>
        <article class="scheduler-card">
          <span>{{ t('tasks.realCollection') }}</span>
          <strong>{{ schedulerStatus.execute_crawler ? t('tasks.on') : t('tasks.off') }}</strong>
        </article>
      </div>
      <div v-if="latestSchedulerHistory.length" class="scheduler-history">
        <article v-for="item in latestSchedulerHistory" :key="`${item.ran_at}-${item.status}`" class="scheduler-history-item">
          <div>
            <strong>{{ labelValue(item.status) }}</strong>
            <span>{{ item.ran_at }}</span>
          </div>
          <span>
            {{ schedulerTriggerLabel(item.trigger_type) }}
            ·
            {{ item.execute_crawler ? t('tasks.schedulerRealRun') : t('tasks.schedulerDryRun') }}
            ·
            {{ t('tasks.resultCount', { count: schedulerResultCount(item) }) }}
          </span>
          <code v-if="item.error">{{ item.error }}</code>
        </article>
      </div>
      <EmptyState v-else :title="t('tasks.noSchedulerHistory')" :description="t('tasks.noSchedulerHistoryDescription')" />
    </BaseSection>

      </aside>

      <main class="task-main-panel">
    <BaseSection :title="t('tasks.listTitle')" :description="t('tasks.listDescription')">
      <template #actions>
        <PermissionGate area="operations" compact>
        <div class="actions">
          <button class="secondary-button" :disabled="schedulerBusy" type="button" @click="dryRunScheduler">
            {{ schedulerBusy ? t('tasks.scanning') : t('tasks.dryRunScheduler') }}
          </button>
          <button class="primary-button" :disabled="schedulerBusy" type="button" @click="runScheduler">
            {{ t('tasks.runScheduler') }}
          </button>
        </div>
        </PermissionGate>
      </template>

      <form class="filter-form" @submit.prevent="applyFilters">
        <label class="field">
          <span>{{ t('tasks.search') }}</span>
          <input v-model="filters.q" :placeholder="t('tasks.searchPlaceholder')" />
        </label>

        <label class="field">
          <span>{{ t('tasks.platform') }}</span>
          <select v-model="filters.platform">
            <option value="">{{ t('tasks.allPlatforms') }}</option>
            <option v-for="item in platformItems" :key="item.platform" :value="item.platform">
              {{ item.label }}
            </option>
          </select>
        </label>

        <label class="field">
          <span>{{ t('tasks.status') }}</span>
          <select v-model="filters.status">
            <option value="">{{ t('tasks.allStatuses') }}</option>
            <option value="draft">{{ t('enum.draft') }}</option>
            <option value="enabled">{{ t('enum.enabled') }}</option>
            <option value="disabled">{{ t('enum.disabled') }}</option>
          </select>
        </label>

        <label class="field">
          <span>{{ t('tasks.mode') }}</span>
          <select v-model="filters.task_mode">
            <option value="">{{ t('tasks.allModes') }}</option>
            <option v-for="item in taskModes" :key="item" :value="item">{{ item }}</option>
          </select>
        </label>

        <label class="field">
          <span>{{ t('tasks.entity') }}</span>
          <select v-model="filters.entity_type">
            <option value="">{{ t('tasks.allEntities') }}</option>
            <option v-for="item in entityTypes" :key="item" :value="item">{{ item }}</option>
          </select>
        </label>

        <label class="field">
          <span>{{ t('tasks.scenario') }}</span>
          <select v-model="filters.scenario_type">
            <option value="">{{ t('tasks.allScenarios') }}</option>
            <option v-for="item in scenarioOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </option>
          </select>
        </label>

        <label class="field">
          <span>{{ t('tasks.limit') }}</span>
          <input v-model.number="filters.limit" min="1" max="500" step="1" type="number" />
        </label>

        <div class="actions filter-actions">
          <button class="primary-button" :disabled="tasksLoading" type="submit">{{ t('tasks.apply') }}</button>
          <button class="secondary-button" :disabled="tasksLoading" type="button" @click="clearFilters">{{ t('tasks.clear') }}</button>
        </div>
      </form>

      <AppAlert v-if="actionMessage" tone="success" :title="t('tasks.successTitle')" :message="actionMessage" />
      <AppAlert v-if="actionError" tone="error" :title="t('tasks.actionFailedTitle')" :message="actionError" />
      <pre v-if="schedulerResult" class="scheduler-result">{{ JSON.stringify(schedulerResult, null, 2) }}</pre>
      <LoadingState v-if="tasksLoading" :title="t('tasks.loadingTasks')" />
      <AppAlert v-else-if="tasksError" tone="error" :title="t('common.loadFailed')" :message="tasksError" />
      <div v-else class="task-list">
        <article v-for="item in taskItems" :key="item.id" class="task-item">
          <div class="task-main">
            <div>
                <strong>{{ item.task_name }}</strong>
          <p>{{ item.platform }} · {{ scenarioLabel(item.scenario_type) }} · {{ item.entity_type }} · {{ item.task_mode }}</p>
            </div>
            <StatusBadge :label="labelValue(item.status)" :tone="statusTone(item.status)" />
          </div>
          <div class="task-meta">
            <span>{{ t('tasks.latestRun', { time: item.last_run_at || '-' }) }}</span>
            <span>{{ item.notes || t('tasks.noNotes') }}</span>
          </div>
          <div v-if="latestRuns(item.id).length" class="run-list">
            <div v-for="run in latestRuns(item.id)" :key="run.id" class="run-row">
              <StatusBadge :label="labelValue(run.status)" :tone="statusTone(run.status)" />
              <span>{{ run.started_at || '-' }}</span>
              <span>{{ t('tasks.datasetCount', { count: run.result_dataset_ids.length }) }}</span>
              <span v-if="run.error_message" class="error-text">{{ run.error_message }}</span>
            </div>
          </div>
          <div v-if="diagnosticsByTask[item.id]" class="diagnostics-panel">
            <div class="diagnostics-head">
              <StatusBadge
                :label="diagnosticsByTask[item.id].ready ? t('tasks.ready') : t('tasks.blocked')"
                :tone="diagnosticsByTask[item.id].ready ? 'success' : 'danger'"
              />
              <span>{{ diagnosticsByTask[item.id].media_crawler_root || '-' }}</span>
            </div>
            <pre>{{ diagnosticCommand(item.id) }}</pre>
            <div v-if="diagnosticsByTask[item.id].errors.length" class="error-text">
              {{ diagnosticsByTask[item.id].errors.join(' · ') }}
            </div>
            <div v-if="diagnosticsByTask[item.id].warnings.length" class="muted">
              {{ diagnosticsByTask[item.id].warnings.join(' · ') }}
            </div>
          </div>
          <div class="task-actions">
            <RouterLink class="secondary-button link-button" :to="{ name: 'task-detail', params: { taskId: item.id } }">
              {{ t('tasks.viewDetail') }}
            </RouterLink>
            <PermissionGate area="operations" compact>
            <button class="secondary-button" type="button" @click="runAction('enable', item.id)">{{ t('tasks.enable') }}</button>
            <button class="secondary-button" type="button" @click="runAction('disable', item.id)">{{ t('tasks.disable') }}</button>
            <button
              class="secondary-button"
              :disabled="diagnosingTaskIds.includes(item.id)"
              type="button"
              @click="diagnoseTask(item.id)"
            >
              {{ diagnosingTaskIds.includes(item.id) ? t('tasks.checking') : t('tasks.diagnoseCrawler') }}
            </button>
            <button
              class="primary-button"
              :disabled="runningTaskIds.includes(item.id)"
              type="button"
              @click="runAction('run', item.id)"
            >
              {{ runningTaskIds.includes(item.id) ? t('tasks.runStarting') : t('tasks.startRun') }}
            </button>
            </PermissionGate>
          </div>
        </article>
        <EmptyState v-if="!taskItems.length" :title="t('tasks.emptyTitle')" :description="t('tasks.emptyDescription')" />
        <PaginationBar
          :total="taskTotal"
          :limit="filters.limit"
          :offset="filters.offset"
          :loading="tasksLoading"
          @change="changeTaskPage"
        />
      </div>
    </BaseSection>
      </main>
    </div>
  </section>
</template>

<style scoped>
.page-grid {
  display: grid;
  gap: 18px;
}

.task-workspace {
  display: grid;
  grid-template-columns: minmax(320px, 380px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.task-side-panel {
  position: sticky;
  top: 86px;
  max-height: calc(100vh - 104px);
  min-width: 0;
  display: grid;
  gap: 16px;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding-right: 2px;
}

.task-main-panel {
  min-width: 0;
}

.task-side-panel .grid-two,
.task-side-panel .scheduler-history-item {
  grid-template-columns: 1fr;
}

.task-side-panel .scheduler-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.task-side-panel .actions {
  display: grid;
}

.task-side-panel .primary-button,
.task-side-panel .secondary-button {
  width: 100%;
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

.section-head h2 {
  margin: 0 0 6px;
}

.section-head p,
.muted,
.task-meta,
.field span {
  color: #64748b;
}

.task-form,
.task-list,
.filter-form {
  display: grid;
  gap: 14px;
}

.grid-two {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.filter-form {
  grid-template-columns: 1.3fr repeat(6, minmax(0, 1fr)) auto;
  align-items: end;
  margin-bottom: 18px;
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

.toggle-row {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.toggle-row label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #334155;
}

.hint-card,
.task-item {
  padding: 16px;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(248, 250, 252, 0.82);
}

.hint-card strong {
  display: block;
  margin-bottom: 8px;
}

.hint-card ul {
  margin: 0;
  padding-left: 18px;
  color: #475569;
}

.actions,
.task-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.filter-actions {
  flex-wrap: nowrap;
}

.task-main {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.task-main strong {
  display: block;
  margin-bottom: 4px;
}

.task-main p,
.task-meta {
  margin: 0;
}

.task-meta {
  display: grid;
  gap: 6px;
  margin: 12px 0;
  font-size: 13px;
}

.run-list {
  display: grid;
  gap: 8px;
  margin-bottom: 12px;
}

.run-row {
  display: grid;
  grid-template-columns: auto minmax(150px, 1fr) auto minmax(0, 1fr);
  gap: 10px;
  align-items: center;
  font-size: 13px;
  color: #475569;
}

.diagnostics-panel {
  display: grid;
  gap: 10px;
  margin-bottom: 12px;
  padding: 12px;
  border-radius: 14px;
  border: 1px solid rgba(203, 213, 225, 0.9);
  background: rgba(255, 255, 255, 0.72);
}

.diagnostics-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  color: #475569;
  font-size: 13px;
}

.diagnostics-panel pre {
  margin: 0;
  padding: 12px;
  overflow: auto;
  border-radius: 12px;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 12px;
}

.scheduler-result {
  margin: 0 0 14px;
  padding: 12px;
  overflow: auto;
  border-radius: 12px;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 12px;
}

.scheduler-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.scheduler-card,
.scheduler-history-item {
  padding: 14px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: var(--radius);
  background: rgba(248, 250, 252, 0.82);
}

.scheduler-card span,
.scheduler-history-item span {
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
}

.scheduler-card strong {
  display: block;
  margin-top: 6px;
  font-size: 22px;
}

.scheduler-history {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.scheduler-history-item {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) auto minmax(0, 1fr);
  gap: 12px;
  align-items: center;
}

.scheduler-history-item div {
  display: grid;
  gap: 3px;
}

.scheduler-history-item code {
  color: #b91c1c;
  overflow-wrap: anywhere;
}

.status-badge {
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.status-badge.failed {
  background: rgba(239, 68, 68, 0.12);
  color: #b91c1c;
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
  align-items: center;
  text-decoration: none;
}

.primary-button:disabled,
.secondary-button:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

.error-text {
  color: #dc2626;
}

.success-text {
  color: #15803d;
}

@media (max-width: 920px) {
  .task-workspace {
    grid-template-columns: 1fr;
  }

  .task-side-panel {
    position: static;
    max-height: none;
    overflow: visible;
    padding-right: 0;
  }

  .grid-two,
  .filter-form {
    grid-template-columns: 1fr;
  }

  .task-main {
    display: grid;
  }

  .section-head {
    display: grid;
  }

  .run-row {
    grid-template-columns: 1fr;
  }

  .scheduler-grid,
  .scheduler-history-item {
    grid-template-columns: 1fr;
  }
}
</style>
