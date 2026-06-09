import { onMounted, ref } from 'vue'
import { listCasesPage, type CaseListFilters } from '../api/cases'
import type { CaseRecord } from '../types'

export function useCases() {
  const items = ref<CaseRecord[]>([])
  const total = ref(0)
  const isLoading = ref(false)
  const error = ref('')

  async function fetchItems(filters?: CaseListFilters) {
    isLoading.value = true
    error.value = ''
    try {
      const result = await listCasesPage(filters)
      items.value = result.cases
      total.value = result.total
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      isLoading.value = false
    }
  }

  onMounted(fetchItems)

  return { items, total, isLoading, error, fetchItems }
}
