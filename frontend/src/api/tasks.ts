import { http } from '../lib/http'
import type { CollectionTask, TaskRun } from '../types'

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

export async function listTasks() {
  const response = await http.get<{ tasks: CollectionTask[] }>('/tasks')
  return response.tasks
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

export async function listTaskRuns(taskId: string) {
  const response = await http.get<{ runs: TaskRun[] }>(`/tasks/${taskId}/runs`)
  return response.runs
}
