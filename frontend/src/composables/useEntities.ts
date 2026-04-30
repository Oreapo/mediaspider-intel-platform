import { onMounted, ref } from 'vue'
import { listEntities, listRelations } from '../api/entities'
import type { EntityRelation, RiskEntity } from '../types'

export function useEntities() {
  const items = ref<RiskEntity[]>([])
  const relations = ref<EntityRelation[]>([])
  const isLoading = ref(false)
  const error = ref('')

  async function fetchItems() {
    isLoading.value = true
    error.value = ''
    try {
      const [entityItems, relationItems] = await Promise.all([listEntities(), listRelations()])
      items.value = entityItems
      relations.value = relationItems
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      isLoading.value = false
    }
  }

  onMounted(fetchItems)

  return { items, relations, isLoading, error, fetchItems }
}
