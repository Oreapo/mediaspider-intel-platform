import { http } from '../lib/http'
import type { DashboardSummary } from '../types'

export async function getDashboardSummary() {
  return http.get<DashboardSummary>('/dashboard/summary')
}
