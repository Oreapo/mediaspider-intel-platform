import { http } from '../lib/http'
import type { AuthUser, LoginResponse } from '../types'

export function login(username: string, password: string) {
  return http.post<LoginResponse>('/auth/login', { username, password })
}

export function getCurrentUser() {
  return http.get<AuthUser>('/auth/me')
}

export function logout() {
  return http.post<{ message: string }>('/auth/logout')
}
