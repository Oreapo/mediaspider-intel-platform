import { http } from '../lib/http'
import type { AuditEvent, RunLogDetail, RunLogEntry } from '../types'

export async function listRunLogs() {
  const response = await http.get<{ logs: RunLogEntry[] }>('/logs/runs')
  return response.logs
}

export async function getRunLog(runId: string, maxLines = 400) {
  return http.get<RunLogDetail>(`/logs/runs/${runId}?max_lines=${maxLines}`)
}

export async function listAuditEvents(
  params: {
    targetType?: string
    targetId?: string
    actorUsername?: string
    action?: string
    q?: string
    createdFrom?: string
    createdTo?: string
    limit?: number
    offset?: number
  } = {},
) {
  const query = new URLSearchParams()
  query.set('limit', String(params.limit ?? 25))
  query.set('offset', String(params.offset ?? 0))
  if (params.targetType) query.set('target_type', params.targetType)
  if (params.targetId) query.set('target_id', params.targetId)
  if (params.actorUsername) query.set('actor_username', params.actorUsername)
  if (params.action) query.set('action', params.action)
  if (params.q) query.set('q', params.q)
  if (params.createdFrom) query.set('created_from', params.createdFrom)
  if (params.createdTo) query.set('created_to', params.createdTo)
  return http.get<{ events: AuditEvent[]; total: number }>(`/logs/audit?${query.toString()}`)
}
