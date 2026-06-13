import { http } from '../lib/http'
import type { AnalysisJob, AnalysisOutput } from '../types'

const ANALYSIS_OUTPUT_JOB_BATCH_SIZE = 100

export interface AnalysisJobCreatePayload {
  dataset_id: string
  analysis_scope: string
  analysis_type: string
  parameters_json?: Record<string, unknown>
}

export interface AnalysisJobListQuery {
  dataset_id?: string
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

export async function getAnalysisOutputsBatch(jobIds: string[]) {
  const uniqueJobIds = Array.from(new Set(jobIds.filter(Boolean)))
  if (!uniqueJobIds.length) return []

  const requests: Array<Promise<AnalysisOutput[]>> = []
  for (let offset = 0; offset < uniqueJobIds.length; offset += ANALYSIS_OUTPUT_JOB_BATCH_SIZE) {
    const params = new URLSearchParams()
    uniqueJobIds
      .slice(offset, offset + ANALYSIS_OUTPUT_JOB_BATCH_SIZE)
      .forEach((jobId) => params.append('job_ids', jobId))
    requests.push(
      http
        .get<{ outputs: AnalysisOutput[] }>(`/analysis/outputs?${params.toString()}`)
        .then((response) => response.outputs),
    )
  }
  return (await Promise.all(requests)).flat()
}
