import { onMounted, ref } from 'vue'
import { listEvidencePacketsPage, type EvidencePacketListQuery } from '../api/evidence'
import type { EvidencePacket } from '../types'

export function useEvidencePackets(initialQuery?: EvidencePacketListQuery) {
  const items = ref<EvidencePacket[]>([])
  const total = ref(0)
  const isLoading = ref(false)
  const error = ref('')

  async function fetchItems(query?: EvidencePacketListQuery) {
    isLoading.value = true
    error.value = ''
    try {
      const result = await listEvidencePacketsPage(query)
      items.value = result.packets
      total.value = result.total
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      isLoading.value = false
    }
  }

  onMounted(() => fetchItems(initialQuery))

  return { items, total, isLoading, error, fetchItems }
}
