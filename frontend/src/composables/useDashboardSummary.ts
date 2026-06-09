import { onMounted, ref } from 'vue'
import { getDashboardSummary } from '../api/dashboard'
import type { DashboardSummary } from '../types'

export function useDashboardSummary() {
  const summary = ref<DashboardSummary | null>(null)
  const isLoading = ref(false)
  const error = ref('')

  async function fetchSummary() {
    isLoading.value = true
    error.value = ''
    try {
      summary.value = await getDashboardSummary()
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      isLoading.value = false
    }
  }

  onMounted(fetchSummary)

  return { summary, isLoading, error, fetchSummary }
}
