import { http } from '../lib/http'
import type { Signal, SignalDetailPayload } from '../types'

export interface SignalCreatePayload {
  dataset_id: string
  task_run_id?: string | null
  signal_type?: string
  signal_source?: string
  risk_level?: string
  risk_score?: number
  summary: string
  payload_json?: Record<string, unknown>
  status?: string
}

export interface SignalExtractionPayload {
  dataset_id: string
  extractors?: string[]
  limit?: number
}

export interface SignalListFilters {
  dataset_id?: string
  status?: string
  risk_level?: string
  signal_type?: string
  q?: string
  limit?: number
  offset?: number
}

export interface SignalListResult {
  signals: Signal[]
  total: number
}

export interface SignalExtractionResult {
  message: string
  signals: Signal[]
  created_count: number
  dedupe_enabled: boolean
}

export interface SignalCluster {
  contact_point: string
  signal_ids: string[]
  signal_count: number
  risk_levels: Record<string, number>
  max_risk_score: number
  // Present on graph-based gang clusters (/signals/gangs).
  cluster_key?: string
  label?: string
  link_types?: string[]
  contact_points?: string[]
  platforms?: string[]
}

function queryString(filters?: SignalListFilters) {
  const params = new URLSearchParams()
  Object.entries(filters || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      params.set(key, String(value))
    }
  })
  const text = params.toString()
  return text ? `?${text}` : ''
}

export function listSignalsPage(filters?: SignalListFilters) {
  return http.get<SignalListResult>(`/signals${queryString(filters)}`)
}

export async function listSignals(filters?: SignalListFilters) {
  return (await listSignalsPage(filters)).signals
}

export async function getSignal(signalId: string) {
  const response = await http.get<{ signal: Signal }>(`/signals/${signalId}`)
  return response.signal
}

export async function getSignalDetail(signalId: string) {
  return http.get<SignalDetailPayload>(`/signals/${signalId}/detail`)
}

export async function createSignal(payload: SignalCreatePayload) {
  const response = await http.post<{ signal: Signal }>('/signals', payload)
  return response.signal
}

export async function extractSignals(payload: SignalExtractionPayload) {
  return http.post<SignalExtractionResult>('/signals/extract', payload)
}

export async function listSignalClusters(datasetId: string) {
  const response = await http.get<{ clusters: SignalCluster[]; total: number }>(
    `/signals/gangs?dataset_id=${encodeURIComponent(datasetId)}`,
  )
  return response.clusters
}

export async function updateSignalStatus(signalId: string, status: string) {
  const response = await http.patch<{ signal: Signal }>(`/signals/${signalId}/status`, { status })
  return response.signal
}

export async function deleteSignal(signalId: string) {
  return http.delete<{ message: string }>(`/signals/${signalId}`)
}
