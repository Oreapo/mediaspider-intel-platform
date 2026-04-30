import { http } from '../lib/http'
import type { CaseDetail, CaseLink, CaseNote, CaseRecord, CaseTimelineItem } from '../types'

export interface CaseCreatePayload {
  case_name: string
  case_type: string
  status?: string
  priority?: string
  summary?: string
  owner?: string
}

export interface CaseUpdatePayload {
  case_name?: string
  case_type?: string
  status?: string
  priority?: string
  summary?: string
  owner?: string
}

export interface CaseLinkCreatePayload {
  link_type: string
  target_id: string
  label?: string
  source_ref_json?: Record<string, unknown>
}

export interface CaseNoteCreatePayload {
  author?: string
  body: string
  note_type?: string
}

export async function listCases() {
  const response = await http.get<{ cases: CaseRecord[] }>('/cases')
  return response.cases
}

export async function createCase(payload: CaseCreatePayload) {
  const response = await http.post<{ case: CaseRecord }>('/cases', payload)
  return response.case
}

export async function updateCase(caseId: string, payload: CaseUpdatePayload) {
  const response = await http.patch<{ case: CaseRecord }>(`/cases/${caseId}`, payload)
  return response.case
}

export async function deleteCase(caseId: string) {
  return http.delete<{ message: string }>(`/cases/${caseId}`)
}

export async function getCaseDetail(caseId: string) {
  return http.get<CaseDetail>(`/cases/${caseId}`)
}

export async function addCaseLink(caseId: string, payload: CaseLinkCreatePayload) {
  const response = await http.post<{ link: CaseLink }>(`/cases/${caseId}/links`, payload)
  return response.link
}

export async function deleteCaseLink(linkId: string) {
  return http.delete<{ message: string }>(`/cases/links/${linkId}`)
}

export async function addCaseNote(caseId: string, payload: CaseNoteCreatePayload) {
  const response = await http.post<{ note: CaseNote }>(`/cases/${caseId}/notes`, payload)
  return response.note
}

export async function deleteCaseNote(noteId: string) {
  return http.delete<{ message: string }>(`/cases/notes/${noteId}`)
}

export async function getCaseTimeline(caseId: string) {
  const response = await http.get<{ timeline: CaseTimelineItem[] }>(`/cases/${caseId}/timeline`)
  return response.timeline
}
