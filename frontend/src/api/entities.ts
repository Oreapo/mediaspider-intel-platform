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

export interface EntityListFilters {
  platform?: string
  entity_type?: string
  status?: string
  min_risk_score?: number
  q?: string
  limit?: number
  offset?: number
}

export interface EntityListResult {
  entities: RiskEntity[]
  total: number
}

function queryString(filters?: EntityListFilters) {
  const params = new URLSearchParams()
  Object.entries(filters || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      params.set(key, String(value))
    }
  })
  const text = params.toString()
  return text ? `?${text}` : ''
}

export function listEntitiesPage(filters?: EntityListFilters) {
  return http.get<EntityListResult>(`/entities${queryString(filters)}`)
}

export async function listEntities(filters?: EntityListFilters) {
  return (await listEntitiesPage(filters)).entities
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
