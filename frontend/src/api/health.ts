import { http } from '../lib/http'

export interface HealthStatus {
  status: string
}

export function fetchHealth() {
  return http.get<HealthStatus>('/health')
}
