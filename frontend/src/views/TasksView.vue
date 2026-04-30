<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { createTask, disableTask, enableTask, listTaskRuns, startTaskRun } from '../api/tasks'
import { usePlatformModels } from '../composables/usePlatformModels'
import { useTasks } from '../composables/useTasks'
import type { PlatformTaskModel, TaskRun } from '../types'

const { items: platformItems } = usePlatformModels()
const {
  items: taskItems,
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
const submitting = ref(false)
const submitError = ref('')
const submitMessage = ref('')
const actionMessage = ref('')
const actionError = ref('')
const runsByTask = ref<Record<string, TaskRun[]>>({})
const runningTaskIds = ref<string[]>([])

const scenarioOptions = [
  { value: 'lead_diversion', label: '引流导流' },
  { value: 'gray_recruitment', label: '灰产招募' },
  { value: 'fraud_promotion', label: '欺诈推广' },
  { value: 'seller_risk', label: '卖家风险' },
  { value: 'product_risk', label: '商品风险' },
  { value: 'topic_watch', label: '主题监测' },
]

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
  if (form.value.task_mode === 'detail') return '详情 ID / URL'
  if (form.value.task_mode === 'creator') return '创作者 ID / URL'
  return '关键词'
})

const inputPlaceholder = computed(() => {
  if (form.value.task_mode === 'detail') return '每行一个详情 ID 或 URL'
  if (form.value.task_mode === 'creator') return '每行一个创作者 ID 或主页链接'
  return '多个关键词使用换行分隔'
})

function toStringList(text: string) {
  return text
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean)
}

async function submitTask() {
  submitting.value = true
  submitError.value = ''
  submitMessage.value = ''
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
    submitMessage.value = 'Task created.'
    form.value.task_name = ''
    form.value.primary_input = ''
    form.value.notes = ''
    await fetchTasks()
  } catch (err) {
    submitError.value = err instanceof Error ? err.message : String(err)
  } finally {
    submitting.value = false
  }
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
      actionMessage.value = run.status === 'succeeded' ? 'Crawler run completed.' : `Crawler run ${run.status}.`
    } else {
      actionMessage.value = `Task ${type}d.`
    }
    await fetchTasks()
  } catch (err) {
    actionError.value = err instanceof Error ? err.message : String(err)
  } finally {
    runningTaskIds.value = runningTaskIds.value.filter((id) => id !== taskId)
  }
}

function latestRuns(taskId: string) {
  return (runsByTask.value[taskId] || []).slice(0, 3)
}
</script>

<template>
  <section class="page-grid">
    <section class="surface section-card">
      <div class="section-head">
        <div>
          <h2>Create Collection Task</h2>
          <p>统一任务模型已经接上平台模板。这里先提供最小可操作录入流。</p>
        </div>
      </div>

      <form class="task-form" @submit.prevent="submitTask">
        <label class="field">
          <span>Task Name</span>
          <input v-model="form.task_name" required placeholder="例：小红书引流线索采集" />
        </label>

        <div class="grid-two">
          <label class="field">
            <span>Platform</span>
            <select v-model="form.platform">
              <option v-for="item in platformItems" :key="item.platform" :value="item.platform">
                {{ item.label }}
              </option>
            </select>
          </label>

          <label class="field">
            <span>Entity Type</span>
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
            <span>Risk Scenario</span>
            <select v-model="form.scenario_type">
              <option v-for="item in scenarioOptions" :key="item.value" :value="item.value">
                {{ item.label }}
              </option>
            </select>
          </label>

          <label class="field">
            <span>Task Mode</span>
            <select v-model="form.task_mode">
              <option v-for="mode in selectedModel?.supported_modes || []" :key="mode" :value="mode">
                {{ mode }}
              </option>
            </select>
          </label>

        </div>

        <label class="field">
          <span>Start Page</span>
          <input v-model.number="form.start_page" min="1" step="1" type="number" />
        </label>

        <label class="field">
          <span>{{ inputLabel }}</span>
          <textarea v-model="form.primary_input" :placeholder="inputPlaceholder" required rows="5" />
        </label>

        <label class="field">
          <span>Signal Extractors</span>
          <input v-model="form.analysis_types" placeholder="risk_terms,contact_points,template_similarity" />
        </label>

        <label class="field">
          <span>Notes</span>
          <textarea v-model="form.notes" placeholder="任务背景、采集目标、分析预期" rows="3" />
        </label>

        <div class="toggle-row">
          <label><input v-model="form.enable_comments" type="checkbox" /> Enable comments</label>
          <label><input v-model="form.enable_sub_comments" type="checkbox" /> Enable sub-comments</label>
          <label><input v-model="form.headless" type="checkbox" /> Headless browser</label>
        </div>

        <div v-if="visibleFieldHints.length" class="hint-card">
          <strong>Platform Hints</strong>
          <ul>
            <li v-for="field in visibleFieldHints" :key="field.key">
              {{ field.label }} · {{ field.group }} · {{ field.control }}
            </li>
          </ul>
        </div>

        <div class="actions">
          <button class="primary-button" :disabled="submitting" type="submit">
            {{ submitting ? 'Creating...' : 'Create Task' }}
          </button>
          <span v-if="submitMessage" class="success-text">{{ submitMessage }}</span>
          <span v-if="submitError" class="error-text">{{ submitError }}</span>
        </div>
      </form>
    </section>

    <section class="surface section-card">
      <div class="section-head">
        <div>
          <h2>Task Registry</h2>
          <p>任务是平台采集、数据沉淀和后续分析的起点。</p>
        </div>
      </div>

      <div v-if="actionMessage" class="success-text">{{ actionMessage }}</div>
      <div v-if="actionError" class="error-text">{{ actionError }}</div>
      <div v-if="tasksLoading" class="muted">Loading tasks...</div>
      <div v-else-if="tasksError" class="error-text">{{ tasksError }}</div>
      <div v-else class="task-list">
        <article v-for="item in taskItems" :key="item.id" class="task-item">
          <div class="task-main">
            <div>
              <strong>{{ item.task_name }}</strong>
          <p>{{ item.platform }} · {{ item.scenario_type }} · {{ item.entity_type }} · {{ item.task_mode }}</p>
            </div>
            <span class="status-badge">{{ item.status }}</span>
          </div>
          <div class="task-meta">
            <span>Last run: {{ item.last_run_at || '-' }}</span>
            <span>{{ item.notes || 'No notes' }}</span>
          </div>
          <div v-if="latestRuns(item.id).length" class="run-list">
            <div v-for="run in latestRuns(item.id)" :key="run.id" class="run-row">
              <span class="status-badge">{{ run.status }}</span>
              <span>{{ run.started_at || '-' }}</span>
              <span>{{ run.result_dataset_ids.length }} dataset(s)</span>
              <span v-if="run.error_message" class="error-text">{{ run.error_message }}</span>
            </div>
          </div>
          <div class="task-actions">
            <button class="secondary-button" type="button" @click="runAction('enable', item.id)">Enable</button>
            <button class="secondary-button" type="button" @click="runAction('disable', item.id)">Disable</button>
            <button
              class="primary-button"
              :disabled="runningTaskIds.includes(item.id)"
              type="button"
              @click="runAction('run', item.id)"
            >
              {{ runningTaskIds.includes(item.id) ? 'Running...' : 'Start Crawler Run' }}
            </button>
          </div>
        </article>
        <div v-if="!taskItems.length" class="muted">No tasks yet.</div>
      </div>
    </section>
  </section>
</template>

<style scoped>
.page-grid {
  display: grid;
  gap: 18px;
}

.section-card {
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
.task-meta,
.field span {
  color: #64748b;
}

.task-form,
.task-list {
  display: grid;
  gap: 14px;
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

.status-badge {
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
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
  .grid-two {
    grid-template-columns: 1fr;
  }

  .task-main {
    display: grid;
  }

  .run-row {
    grid-template-columns: 1fr;
  }
}
</style>
