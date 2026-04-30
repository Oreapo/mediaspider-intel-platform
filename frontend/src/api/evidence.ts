import { http } from '../lib/http'
import type { EvidencePacket } from '../types'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

export interface EvidencePacketCreatePayload {
  case_id: string
  packet_name: string
}

export async function listEvidencePackets() {
  const response = await http.get<{ packets: EvidencePacket[] }>('/evidence')
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

export function evidenceDownloadUrl(packetId: string) {
  return `${BASE_URL}/evidence/${packetId}/download`
}
