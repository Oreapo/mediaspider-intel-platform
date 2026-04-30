import { onMounted, ref } from 'vue'
import { listAnalysisJobs } from '../api/analysis'
import type { AnalysisJob } from '../types'

export function useAnalysisJobs() {
  const items = ref<AnalysisJob[]>([])
  const isLoading = ref(false)
  const error = ref('')

  async function fetchItems() {
    isLoading.value = true
    error.value = ''
    try {
      items.value = await listAnalysisJobs()
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      isLoading.value = false
    }
  }

  onMounted(fetchItems)

  return { items, isLoading, error, fetchItems }
}
