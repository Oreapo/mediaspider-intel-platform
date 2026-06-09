import { onMounted, ref } from 'vue'
import { listPlatformProfiles } from '../api/platforms'
import type { PlatformProfile } from '../types'

export function usePlatformProfiles(platform = '') {
  const profiles = ref<PlatformProfile[]>([])
  const isLoading = ref(false)
  const error = ref('')

  async function fetchProfiles(nextPlatform = platform) {
    isLoading.value = true
    error.value = ''
    try {
      profiles.value = await listPlatformProfiles(nextPlatform)
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      isLoading.value = false
    }
  }

  onMounted(() => fetchProfiles())

  return { profiles, isLoading, error, fetchProfiles }
}
