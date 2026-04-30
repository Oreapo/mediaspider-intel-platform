import { http } from '../lib/http'
import type { PlatformTaskModel } from '../types'

export async function listPlatformTaskModels() {
  return http.get<PlatformTaskModel[]>('/platforms')
}
