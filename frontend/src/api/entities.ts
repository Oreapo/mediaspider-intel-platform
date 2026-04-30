import { http } from '../lib/http'
import type { EntityDetail, EntityRelation, RiskEntity } from '../types'

export interface EntityCreatePayload {
  entity_type: string
  display_name: string
  platform: string
  source_ref?: Record<string, unknown>
  risk_score?: number
  status?: string
  profile_json?: Record<string, unknown>
}

export interface EntityFromSignalPayload {
  signal_id: string
  entity_type?: string | null
  display_name?: string | null
}

export interface EntityRelationCreatePayload {
  source_entity_id: string
  target_entity_id: string
  relation_type: string
  confidence: number
  evidence_ref_json?: Record<string, unknown>
}

export interface EntityMergePayload {
  source_entity_id: string
  target_entity_id: string
  relation_type?: string
  confidence?: number
  evidence_ref_json?: Record<string, unknown>
}

export async function listEntities() {
  const response = await http.get<{ entities: RiskEntity[] }>('/entities')
  return response.entities
}

export async function getEntityDetail(entityId: string) {
  return http.get<EntityDetail>(`/entities/${entityId}`)
}

export async function createEntity(payload: EntityCreatePayload) {
  const response = await http.post<{ entity: RiskEntity }>('/entities', payload)
  return response.entity
}

export async function createEntityFromSignal(payload: EntityFromSignalPayload) {
  const response = await http.post<{ entity: RiskEntity }>('/entities/from-signal', payload)
  return response.entity
}

export async function updateEntityStatus(entityId: string, status: string) {
  const response = await http.patch<{ entity: RiskEntity }>(`/entities/${entityId}/status`, { status })
  return response.entity
}

export async function deleteEntity(entityId: string) {
  return http.delete<{ message: string }>(`/entities/${entityId}`)
}

export async function listRelations() {
  const response = await http.get<{ relations: EntityRelation[] }>('/entities/relations')
  return response.relations
}

export async function createRelation(payload: EntityRelationCreatePayload) {
  const response = await http.post<{ relation: EntityRelation }>('/entities/relations', payload)
  return response.relation
}

export async function mergeEntities(payload: EntityMergePayload) {
  return http.post<{
    source_entity: RiskEntity
    target_entity: RiskEntity
    relation: EntityRelation
  }>('/entities/merge', payload)
}
