import { http } from '../lib/http'
import type { PlatformProfile, PlatformProfileDiagnostics, PlatformTaskModel } from '../types'

export async function listPlatformTaskModels() {
  return http.get<PlatformTaskModel[]>('/platforms')
}

export interface PlatformProfilePayload {
  platform: string
  profile_name: string
  auth_type: string
  credentials_ref?: string
  settings_json?: Record<string, unknown>
}

export async function listPlatformProfiles(platform = '') {
  const query = platform ? `?platform=${encodeURIComponent(platform)}` : ''
  const response = await http.get<{ profiles: PlatformProfile[] }>(`/platforms/profiles${query}`)
  return response.profiles
}

export async function createPlatformProfile(payload: PlatformProfilePayload) {
  return http.post<{ message: string; profile: PlatformProfile }>('/platforms/profiles', payload)
}

export async function updatePlatformProfile(profileId: string, payload: Partial<PlatformProfilePayload>) {
  return http.patch<{ message: string; profile: PlatformProfile }>(`/platforms/profiles/${profileId}`, payload)
}

export async function deletePlatformProfile(profileId: string) {
  return http.delete<{ message: string }>(`/platforms/profiles/${profileId}`)
}

export async function diagnosePlatformProfile(profileId: string) {
  const response = await http.get<{ diagnostics: PlatformProfileDiagnostics }>(
    `/platforms/profiles/${profileId}/diagnostics`,
  )
  return response.diagnostics
}
