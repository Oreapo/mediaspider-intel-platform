import { http } from '../lib/http'
import type { AnalysisJob, AnalysisOutput } from '../types'

export interface AnalysisJobCreatePayload {
  dataset_id: string
  analysis_scope: string
  analysis_type: string
  parameters_json?: Record<string, unknown>
}

export async function listAnalysisJobs() {
  const response = await http.get<{ jobs: AnalysisJob[] }>('/analysis/jobs')
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
