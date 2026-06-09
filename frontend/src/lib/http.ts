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

export function apiDownloadUrl(path: string) {
  const token = getAuthToken()
  const url = new URL(apiUrl(path))
  if (token) url.searchParams.set('access_token', token)
  return url.toString()
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  const token = getAuthToken()
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(apiUrl(path), {
    ...init,
    headers,
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    if (response.status === 401) clearAuthToken()
    throw new Error(errorMessageFromPayload(data) || 'Request failed')
  }
  return data as T
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
