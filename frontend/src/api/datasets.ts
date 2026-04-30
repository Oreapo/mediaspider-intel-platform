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

export async function listDatasets() {
  const response = await http.get<{ datasets: Dataset[] }>('/datasets')
  return response.datasets
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
