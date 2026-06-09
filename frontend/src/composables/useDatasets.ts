import { onMounted, ref } from 'vue'
import { listDatasetsPage, type DatasetListFilters } from '../api/datasets'
import type { Dataset } from '../types'

export function useDatasets() {
  const items = ref<Dataset[]>([])
  const total = ref(0)
  const isLoading = ref(false)
  const error = ref('')

  async function fetchItems(filters?: DatasetListFilters) {
    isLoading.value = true
    error.value = ''
    try {
      const result = await listDatasetsPage(filters)
      items.value = result.datasets
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
