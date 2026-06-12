import { http } from '../lib/http'
import type { AnalysisJob, AnalysisOutput } from '../types'

export interface AnalysisJobCreatePayload {
  dataset_id: string
  analysis_scope: string
  analysis_type: string
  parameters_json?: Record<string, unknown>
}

export interface AnalysisJobListQuery {
  limit?: number
  offset?: number
}

export interface AnalysisJobListResult {
  jobs: AnalysisJob[]
  total: number
}

function queryString(query?: AnalysisJobListQuery) {
  const params = new URLSearchParams()
  Object.entries(query || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null) params.set(key, String(value))
  })
  const text = params.toString()
  return text ? `?${text}` : ''
}

export async function listAnalysisJobsPage(query?: AnalysisJobListQuery) {
  return http.get<AnalysisJobListResult>(`/analysis/jobs${queryString(query)}`)
}

export async function listAnalysisJobs(query?: AnalysisJobListQuery) {
  const response = await listAnalysisJobsPage(query)
  return response.jobs
}

export async function createAnalysisJob(payload: AnalysisJobCreatePayload) {
  const response = await http.post<{ job: AnalysisJob }>('/analysis/jobs', payload)
  return response.job
}

export async function getAnalysisOutputs(jobId: string) {
  const response = await http.get<{ outputs: AnalysisOutput[] }>(`/analysis/jobs/${jobId}/outputs`)
  return response.outputs
}
