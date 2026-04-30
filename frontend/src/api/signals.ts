import { http } from '../lib/http'
import type { Signal } from '../types'

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

export async function listSignals() {
  const response = await http.get<{ signals: Signal[] }>('/signals')
  return response.signals
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
