import { translate } from './useI18n'

// Shared enum label resolver: returns the i18n label for `enum.<value>`,
// falling back to the raw value when no translation exists. Replaces the
// per-view `labelValue` helper that was duplicated across 12 views.
export function enumLabel(value: string): string {
  const key = `enum.${value}`
  const translated = translate(key)
  return translated === key ? value : translated
}

// Shared scenario label resolver: `scenario.<value>` with raw-value fallback.
// Returns '-' for empty input (superset of the per-view variants it replaces).
export function scenarioLabel(value?: string | null): string {
  if (!value) return '-'
  const key = `scenario.${value}`
  const translated = translate(key)
  return translated === key ? value : translated
}
