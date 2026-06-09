import { onMounted, ref } from 'vue'
import { listTasksPage, type TaskListFilters } from '../api/tasks'
import type { CollectionTask } from '../types'

export function useTasks() {
  const items = ref<CollectionTask[]>([])
  const total = ref(0)
  const isLoading = ref(false)
  const error = ref('')

  async function fetchItems(filters?: TaskListFilters) {
    isLoading.value = true
    error.value = ''
    try {
      const result = await listTasksPage(filters)
      items.value = result.tasks
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
