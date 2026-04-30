import { onMounted, ref } from 'vue'
import { listDatasets } from '../api/datasets'
import type { Dataset } from '../types'

export function useDatasets() {
  const items = ref<Dataset[]>([])
  const isLoading = ref(false)
  const error = ref('')

  async function fetchItems() {
    isLoading.value = true
    error.value = ''
    try {
      items.value = await listDatasets()
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      isLoading.value = false
    }
  }

  onMounted(fetchItems)

  return { items, isLoading, error, fetchItems }
}
