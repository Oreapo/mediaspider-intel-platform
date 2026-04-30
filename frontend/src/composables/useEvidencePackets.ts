import { onMounted, ref } from 'vue'
import { listEvidencePackets } from '../api/evidence'
import type { EvidencePacket } from '../types'

export function useEvidencePackets() {
  const items = ref<EvidencePacket[]>([])
  const isLoading = ref(false)
  const error = ref('')

  async function fetchItems() {
    isLoading.value = true
    error.value = ''
    try {
      items.value = await listEvidencePackets()
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      isLoading.value = false
    }
  }

  onMounted(fetchItems)

  return { items, isLoading, error, fetchItems }
}
