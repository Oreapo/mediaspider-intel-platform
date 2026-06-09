import { http } from '../lib/http'
import type { NotificationDelivery, NotificationInboxItem, NotificationRule } from '../types'

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

export interface NotificationDeliveryQuery {
  rule_id?: string
  status?: string
  channel?: string
  target_type?: string
  q?: string
  limit?: number
  offset?: number
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

export async function listNotificationDeliveries(query: NotificationDeliveryQuery = {}) {
  const params = new URLSearchParams()
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      params.set(key, String(value))
    }
  })
  const suffix = params.toString() ? `?${params.toString()}` : ''
  const response = await http.get<{ deliveries: NotificationDelivery[]; total: number }>(
    `/notifications/deliveries${suffix}`,
  )
  return response.deliveries
}

export async function retryNotificationDelivery(deliveryId: string) {
  const response = await http.post<{ delivery: NotificationDelivery }>(`/notifications/deliveries/${deliveryId}/retry`)
  return response.delivery
}

export interface NotificationInboxQuery {
  unread_only?: boolean
  q?: string
  limit?: number
  offset?: number
}

export async function listNotificationInbox(query: NotificationInboxQuery = {}) {
  const params = new URLSearchParams()
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      params.set(key, String(value))
    }
  })
  const suffix = params.toString() ? `?${params.toString()}` : ''
  return http.get<{ items: NotificationInboxItem[]; total: number; unread_count: number }>(
    `/notifications/inbox${suffix}`,
  )
}

export async function updateNotificationInboxItem(deliveryId: string, read: boolean) {
  const response = await http.patch<{ item: NotificationInboxItem }>(`/notifications/inbox/${deliveryId}`, { read })
  return response.item
}

export async function markAllNotificationInboxRead() {
  return http.post<{ updated_count: number }>('/notifications/inbox/mark-all-read')
}

export async function runScheduledNotifications(now?: string) {
  return http.post<{
    ran_at: string
    results: Array<Record<string, unknown>>
  }>('/notifications/run-scheduled', { now: now || null })
}
