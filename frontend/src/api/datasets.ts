import { http } from '../lib/http'
import type { Dataset, DatasetPreview } from '../types'

export interface DatasetCreatePayload {
  dataset_name: string
  dataset_type: string
  source_platform: string
  source_task_id?: string | null
  source_run_id?: string | null
  scenario_type?: string | null
  storage_uri?: string
  tags?: string[]
}

export interface DatasetListFilters {
  source_platform?: string
  dataset_type?: string
  scenario_type?: string
  tag?: string
  q?: string
  limit?: number
  offset?: number
}

export interface DatasetListResult {
  datasets: Dataset[]
  total: number
}

function queryString(filters?: DatasetListFilters) {
  const params = new URLSearchParams()
  Object.entries(filters || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      params.set(key, String(value))
    }
  })
  const text = params.toString()
  return text ? `?${text}` : ''
}

export function listDatasetsPage(filters?: DatasetListFilters) {
  return http.get<DatasetListResult>(`/datasets${queryString(filters)}`)
}

export async function listDatasets(filters?: DatasetListFilters) {
  return (await listDatasetsPage(filters)).datasets
}

export async function getDataset(datasetId: string) {
  const response = await http.get<{ dataset: Dataset }>(`/datasets/${datasetId}`)
  return response.dataset
}

export async function createDataset(payload: DatasetCreatePayload) {
  const response = await http.post<{ dataset: Dataset }>('/datasets', payload)
  return response.dataset
}

export async function deleteDataset(datasetId: string) {
  return http.delete<{ message: string }>(`/datasets/${datasetId}`)
}

export async function previewDataset(datasetId: string, limit = 50) {
  return http.get<DatasetPreview>(`/datasets/${datasetId}/preview?limit=${limit}`)
}
