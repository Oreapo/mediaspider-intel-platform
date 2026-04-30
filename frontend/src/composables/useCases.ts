import { onMounted, ref } from 'vue'
import { listCases } from '../api/cases'
import type { CaseRecord } from '../types'

export function useCases() {
  const items = ref<CaseRecord[]>([])
  const isLoading = ref(false)
  const error = ref('')

  async function fetchItems() {
    isLoading.value = true
    error.value = ''
    try {
      items.value = await listCases()
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      isLoading.value = false
    }
  }

  onMounted(fetchItems)

  return { items, isLoading, error, fetchItems }
}
