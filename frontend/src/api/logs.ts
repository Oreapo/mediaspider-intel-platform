import { http } from '../lib/http'
import type { RunLogDetail, RunLogEntry } from '../types'

export async function listRunLogs() {
  const response = await http.get<{ logs: RunLogEntry[] }>('/logs/runs')
  return response.logs
}

export async function getRunLog(runId: string, maxLines = 400) {
  return http.get<RunLogDetail>(`/logs/runs/${runId}?max_lines=${maxLines}`)
}
