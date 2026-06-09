import { onMounted, ref } from 'vue'
import { listSignalsPage, type SignalListFilters } from '../api/signals'
import type { Signal } from '../types'

export function useSignals() {
  const items = ref<Signal[]>([])
  const total = ref(0)
  const isLoading = ref(false)
  const error = ref('')

  async function fetchItems(filters?: SignalListFilters) {
    isLoading.value = true
    error.value = ''
    try {
      const result = await listSignalsPage(filters)
      items.value = result.signals
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
