const BASE_URL = normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL || '/api')
const TOKEN_KEY = 'mediaspider_auth_token'

function normalizeBaseUrl(baseUrl: string) {
  const normalized = baseUrl.trim().replace(/\/+$/, '')
  return normalized || '/'
}

export function apiUrl(path: string) {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  const joinedPath = BASE_URL === '/' ? normalizedPath : `${BASE_URL}${normalizedPath}`
  return new URL(joinedPath, window.location.origin).toString()
}

export function getAuthToken() {
  return window.localStorage.getItem(TOKEN_KEY)
}

export function setAuthToken(token: string) {
  window.localStorage.setItem(TOKEN_KEY, token)
}

export function clearAuthToken() {
  window.localStorage.removeItem(TOKEN_KEY)
}

function errorMessageFromPayload(payload: unknown) {
  if (!payload || typeof payload !== 'object') return undefined
  const data = payload as { detail?: unknown; message?: unknown }
  return formatErrorDetail(data.detail) || formatErrorDetail(data.message)
}

function formatErrorDetail(detail: unknown): string | undefined {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const messages = detail.map((item) => formatErrorDetail(item)).filter(Boolean)
    return messages.length ? messages.join('; ') : undefined
  }
  if (!detail || typeof detail !== 'object') return undefined

  const record = detail as Record<string, unknown>
  if (typeof record.msg === 'string') {
    const location = Array.isArray(record.loc) ? record.loc.map(String).join('.') : ''
    return location ? `${location}: ${record.msg}` : record.msg
  }
  if (typeof record.message === 'string') return record.message
  if (typeof record.detail === 'string') return record.detail
  return undefined
}

async function authorizedFetch(path: string, init?: RequestInit) {
  const headers = new Headers(init?.headers)
  const token = getAuthToken()
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  return fetch(apiUrl(path), {
    ...init,
    headers,
  })
}

async function responseError(response: Response) {
  const data = await response.json().catch(() => ({}))
  if (response.status === 401) clearAuthToken()
  return new Error(errorMessageFromPayload(data) || 'Request failed')
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await authorizedFetch(path, init)
  if (!response.ok) throw await responseError(response)
  const data = await response.json().catch(() => ({}))
  return data as T
}

function downloadFilename(contentDisposition: string | null, fallbackFilename: string) {
  if (!contentDisposition) return fallbackFilename

  const encoded = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  if (encoded) {
    try {
      return decodeURIComponent(encoded.replace(/^"|"$/g, ''))
    } catch {
      return encoded
    }
  }

  return contentDisposition.match(/filename="?([^";]+)"?/i)?.[1] || fallbackFilename
}

export async function downloadApiFile(path: string, fallbackFilename: string) {
  const response = await authorizedFetch(path)
  if (!response.ok) throw await responseError(response)

  const blob = await response.blob()
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = downloadFilename(response.headers.get('Content-Disposition'), fallbackFilename)
  link.hidden = true
  document.body.append(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0)
}

export const http = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'POST',
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'PATCH',
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),
  delete: <T>(path: string) =>
    request<T>(path, {
      method: 'DELETE',
    }),
}
