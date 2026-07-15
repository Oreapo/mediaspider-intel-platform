import { ref } from 'vue'

export type Theme = 'blue' | 'pink'

const storageKey = 'mediaspider_theme'
const defaultTheme: Theme = 'blue'

export const themeOptions: Array<{ value: Theme; label: string }> = [
  { value: 'blue', label: '蓝' },
  { value: 'pink', label: '粉' },
]

function getInitialTheme(): Theme {
  if (typeof window === 'undefined') return defaultTheme
  const stored = window.localStorage.getItem(storageKey)
  return stored === 'pink' || stored === 'blue' ? stored : defaultTheme
}

const theme = ref<Theme>(getInitialTheme())

function applyTheme(next: Theme) {
  if (typeof document !== 'undefined') {
    document.documentElement.dataset.theme = next
    const favicon = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
    if (favicon) {
      favicon.href = next === 'pink' ? '/brand/logo-pink.png' : '/brand/logo-blue.png'
    }
  }
}

applyTheme(theme.value)

export function setTheme(next: Theme) {
  theme.value = next
  applyTheme(next)
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(storageKey, next)
  }
}

export function useTheme() {
  return { theme, themeOptions, setTheme }
}
