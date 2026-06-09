import { http } from '../lib/http'
import type { CollectionTask, CrawlerDiagnostics, SchedulerStatus, TaskRun } from '../types'

export interface TaskCreatePayload {
  task_name: string
  platform: string
  entity_type: string
  task_mode: string
  scenario_type: string
  status?: string
  auth_profile_id?: string | null
  task_payload_json?: Record<string, unknown>
  filter_payload_json?: Record<string, unknown>
  runtime_payload_json?: Record<string, unknown>
  storage_profile_json?: Record<string, unknown>
  analysis_profile_json?: Record<string, unknown>
  notes?: string
}

export interface TaskListFilters {
  platform?: string
  status?: string
  task_mode?: string
  entity_type?: string
  scenario_type?: string
  q?: string
  limit?: number
  offset?: number
}

export interface TaskListResult {
  tasks: CollectionTask[]
  total: number
}

function queryString(filters?: TaskListFilters) {
  const params = new URLSearchParams()
  Object.entries(filters || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      params.set(key, String(value))
    }
  })
  const text = params.toString()
  return text ? `?${text}` : ''
}

export function listTasksPage(filters?: TaskListFilters) {
  return http.get<TaskListResult>(`/tasks${queryString(filters)}`)
}

export async function listTasks(filters?: TaskListFilters) {
  return (await listTasksPage(filters)).tasks
}

export async function getTask(taskId: string) {
  const response = await http.get<{ task: CollectionTask }>(`/tasks/${taskId}`)
  return response.task
}

export async function createTask(payload: TaskCreatePayload) {
  const response = await http.post<{ task: CollectionTask }>('/tasks', payload)
  return response.task
}

export async function enableTask(taskId: string) {
  const response = await http.post<{ task: CollectionTask }>(`/tasks/${taskId}/enable`)
  return response.task
}

export async function disableTask(taskId: string) {
  const response = await http.post<{ task: CollectionTask }>(`/tasks/${taskId}/disable`)
  return response.task
}

export async function startTaskRun(taskId: string) {
  const response = await http.post<{ run: TaskRun }>(`/tasks/${taskId}/runs`, {
    execute_crawler: true,
    trigger_type: 'manual',
  })
  return response.run
}

export async function runScheduledTasks(executeCrawler = true) {
  return http.post<{
    ran_at: string
    results: Array<Record<string, unknown>>
  }>('/tasks/run-scheduled', {
    execute_crawler: executeCrawler,
  })
}

export async function getSchedulerStatus() {
  return http.get<SchedulerStatus>('/tasks/scheduler/status')
}

export async function listTaskRuns(taskId: string) {
  const response = await http.get<{ runs: TaskRun[] }>(`/tasks/${taskId}/runs`)
  return response.runs
}

export async function getCrawlerDiagnostics(taskId: string) {
  const response = await http.get<{ diagnostics: CrawlerDiagnostics }>(`/tasks/${taskId}/crawler-diagnostics`)
  return response.diagnostics
}
