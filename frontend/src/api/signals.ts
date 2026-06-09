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
  const response = await http.post<{ signals: Signal[] }>('/signals/extract', payload)
  return response.signals
}

export async function updateSignalStatus(signalId: string, status: string) {
  const response = await http.patch<{ signal: Signal }>(`/signals/${signalId}/status`, { status })
  return response.signal
}

export async function deleteSignal(signalId: string) {
  return http.delete<{ message: string }>(`/signals/${signalId}`)
}
