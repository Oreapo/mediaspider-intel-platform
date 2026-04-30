import { http } from '../lib/http'
import type { NotificationDelivery, NotificationRule } from '../types'

export interface NotificationRulePayload {
  rule_name: string
  enabled?: boolean
  event_type?: string
  risk_level_threshold?: string
  scenario_types?: string[]
  platforms?: string[]
  channels?: string[]
  cron_expr?: string
  cooldown_minutes?: number
  channel_config_json?: Record<string, unknown>
}

export async function listNotificationRules() {
  const response = await http.get<{ rules: NotificationRule[] }>('/notifications/rules')
  return response.rules
}

export async function createNotificationRule(payload: NotificationRulePayload) {
  const response = await http.post<{ rule: NotificationRule }>('/notifications/rules', payload)
  return response.rule
}

export async function updateNotificationRule(ruleId: string, payload: Partial<NotificationRulePayload>) {
  const response = await http.patch<{ rule: NotificationRule }>(`/notifications/rules/${ruleId}`, payload)
  return response.rule
}

export async function deleteNotificationRule(ruleId: string) {
  return http.delete<{ message: string }>(`/notifications/rules/${ruleId}`)
}

export async function listNotificationDeliveries() {
  const response = await http.get<{ deliveries: NotificationDelivery[] }>('/notifications/deliveries')
  return response.deliveries
}

export async function runScheduledNotifications(now?: string) {
  return http.post<{
    ran_at: string
    results: Array<Record<string, unknown>>
  }>('/notifications/run-scheduled', { now: now || null })
}
