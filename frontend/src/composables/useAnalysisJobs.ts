import { onMounted, ref } from 'vue'
import { listAnalysisJobsPage, type AnalysisJobListQuery } from '../api/analysis'
import type { AnalysisJob } from '../types'

export function useAnalysisJobs(initialQuery?: AnalysisJobListQuery) {
  const items = ref<AnalysisJob[]>([])
  const total = ref(0)
  const isLoading = ref(false)
  const error = ref('')

  async function fetchItems(query?: AnalysisJobListQuery) {
    isLoading.value = true
    error.value = ''
    try {
      const result = await listAnalysisJobsPage(query)
      items.value = result.jobs
      total.value = result.total
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      isLoading.value = false
    }
  }

  onMounted(() => fetchItems(initialQuery))

  return { items, total, isLoading, error, fetchItems }
}
