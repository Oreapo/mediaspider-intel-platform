import { onMounted, ref } from 'vue'
import { listReportsPage, type ReportListQuery } from '../api/reports'
import type { Report } from '../types'

export function useReports(initialQuery?: ReportListQuery) {
  const items = ref<Report[]>([])
  const total = ref(0)
  const isLoading = ref(false)
  const error = ref('')

  async function fetchItems(query?: ReportListQuery) {
    isLoading.value = true
    error.value = ''
    try {
      const result = await listReportsPage(query)
      items.value = result.reports
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
