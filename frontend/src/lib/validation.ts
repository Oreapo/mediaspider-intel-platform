import { translate } from '../composables/useI18n'

export type ValidationErrors = Record<string, string>

export function required(value: unknown, label: string) {
  if (typeof value === 'string') {
    return value.trim() ? '' : translate('validation.required', { label })
  }
  return value === undefined || value === null ? translate('validation.required', { label }) : ''
}

export function parseJsonObject(text: string, label = 'JSON') {
  if (!text.trim()) return { value: {} as Record<string, unknown> }

  try {
    const parsed = JSON.parse(text)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return { error: translate('validation.jsonObject', { label }) }
    }
    return { value: parsed as Record<string, unknown> }
  } catch (err) {
    const reason = err instanceof Error ? err.message : String(err)
    return { error: translate('validation.jsonInvalid', { label, reason }) }
  }
}

export function httpUrl(value: string, label: string) {
  const normalized = value.trim()
  if (!normalized) return ''
  if (/^https?:\/\/\S+$/i.test(normalized)) return ''
  return translate('validation.httpUrl', { label })
}

export function nonNegativeNumber(value: number, label: string) {
  return Number.isFinite(value) && value >= 0 ? '' : translate('validation.nonNegativeNumber', { label })
}
