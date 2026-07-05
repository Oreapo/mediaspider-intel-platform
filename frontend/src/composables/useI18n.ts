import { computed, ref } from 'vue'
import { defaultLocale, localeOptions, messages, type Locale } from '../i18n/messages'

const storageKey = 'mediaspider_locale'

function isLocale(value: string | null): value is Locale {
  return Boolean(value && value in messages)
}

function getInitialLocale(): Locale {
  if (typeof window === 'undefined') return defaultLocale
  const stored = window.localStorage.getItem(storageKey)
  if (isLocale(stored)) return stored
  const browserLocale = window.navigator.language
  if (browserLocale.startsWith('en')) return 'en-US'
  return defaultLocale
}

const locale = ref<Locale>(getInitialLocale())

function applyDocumentLocale(nextLocale: Locale) {
  if (typeof document === 'undefined') return
  document.documentElement.lang = nextLocale
}

applyDocumentLocale(locale.value)

export function translate(key: string, params?: Record<string, string | number>) {
  const template = messages[locale.value][key] ?? messages[defaultLocale][key] ?? key
  if (!params) return template
  return template.replace(/\{(\w+)\}/g, (_, name: string) => String(params[name] ?? `{${name}}`))
}

export function setLocale(nextLocale: Locale) {
  locale.value = nextLocale
  applyDocumentLocale(nextLocale)
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(storageKey, nextLocale)
  }
}

export function getLocalizedRouteTitle(titleKey?: string) {
  const appName = translate('app.documentTitle')
  return titleKey ? `${translate(titleKey)} - ${appName}` : appName
}

export function useI18n() {
  return {
    locale,
    localeOptions,
    currentLocaleLabel: computed(
      () => localeOptions.find((option) => option.value === locale.value)?.label ?? locale.value,
    ),
    setLocale,
    t: translate,
  }
}
