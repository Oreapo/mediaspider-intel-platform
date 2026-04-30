import { onMounted, ref } from 'vue'
import { listPlatformTaskModels } from '../api/platforms'
import type { PlatformTaskModel } from '../types'

export function usePlatformModels() {
  const items = ref<PlatformTaskModel[]>([])
  const isLoading = ref(false)
  const error = ref('')

  async function fetchItems() {
    isLoading.value = true
    error.value = ''
    try {
      items.value = await listPlatformTaskModels()
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      isLoading.value = false
    }
  }

  onMounted(fetchItems)

  return { items, isLoading, error, fetchItems }
}
