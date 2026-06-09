import { onMounted, ref } from 'vue'
import { listEntitiesPage, listRelations, type EntityListFilters } from '../api/entities'
import type { EntityRelation, RiskEntity } from '../types'

export function useEntities() {
  const items = ref<RiskEntity[]>([])
  const total = ref(0)
  const relations = ref<EntityRelation[]>([])
  const isLoading = ref(false)
  const error = ref('')

  async function fetchItems(filters?: EntityListFilters) {
    isLoading.value = true
    error.value = ''
    try {
      const [result, relationItems] = await Promise.all([listEntitiesPage(filters), listRelations()])
      items.value = result.entities
      total.value = result.total
      relations.value = relationItems
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      isLoading.value = false
    }
  }

  onMounted(fetchItems)

  return { items, total, relations, isLoading, error, fetchItems }
}
