import { onMounted, ref } from 'vue'
import { listReports } from '../api/reports'
import type { Report } from '../types'

export function useReports() {
  const items = ref<Report[]>([])
  const isLoading = ref(false)
  const error = ref('')

  async function fetchItems() {
    isLoading.value = true
    error.value = ''
    try {
      items.value = await listReports()
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      isLoading.value = false
    }
  }

  onMounted(fetchItems)

  return { items, isLoading, error, fetchItems }
}
