import { downloadApiFile, http } from '../lib/http'
import type { EvidencePacket } from '../types'

export interface EvidencePacketCreatePayload {
  case_id: string
  packet_name: string
}

export interface EvidencePacketListQuery {
  limit?: number
  offset?: number
}

export interface EvidencePacketListResult {
  packets: EvidencePacket[]
  total: number
}

function queryString(query?: EvidencePacketListQuery) {
  const params = new URLSearchParams()
  Object.entries(query || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null) params.set(key, String(value))
  })
  const text = params.toString()
  return text ? `?${text}` : ''
}

export async function listEvidencePacketsPage(query?: EvidencePacketListQuery) {
  return http.get<EvidencePacketListResult>(`/evidence${queryString(query)}`)
}

export async function listEvidencePackets(query?: EvidencePacketListQuery) {
  const response = await listEvidencePacketsPage(query)
  return response.packets
}

export async function generateEvidencePacket(payload: EvidencePacketCreatePayload) {
  const response = await http.post<{ packet: EvidencePacket }>('/evidence/packets', payload)
  return response.packet
}

export async function getEvidencePacket(packetId: string) {
  const response = await http.get<{ packet: EvidencePacket }>(`/evidence/${packetId}`)
  return response.packet
}

export async function deleteEvidencePacket(packetId: string, deleteStorage = false) {
  const suffix = deleteStorage ? '?delete_storage=true' : ''
  return http.delete<{ message: string }>(`/evidence/${packetId}${suffix}`)
}

export function downloadEvidencePacket(packetId: string) {
  return downloadApiFile(`/evidence/${packetId}/download`, `evidence-${packetId}.json`)
}
