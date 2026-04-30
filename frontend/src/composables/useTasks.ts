import { onMounted, ref } from 'vue'
import { listTasks } from '../api/tasks'
import type { CollectionTask } from '../types'

export function useTasks() {
  const items = ref<CollectionTask[]>([])
  const isLoading = ref(false)
  const error = ref('')

  async function fetchItems() {
    isLoading.value = true
    error.value = ''
    try {
      items.value = await listTasks()
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      isLoading.value = false
    }
  }

  onMounted(fetchItems)

  return { items, isLoading, error, fetchItems }
}
