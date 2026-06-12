import { downloadApiFile, http } from '../lib/http'
import type { Report } from '../types'

export interface ReportGeneratePayload {
  case_id: string
  report_name: string
  report_type?: string
}

export interface ReportUpdatePayload {
  report_name?: string
  status?: string
  content_markdown?: string
}

export interface ReportListQuery {
  limit?: number
  offset?: number
}

export interface ReportListResult {
  reports: Report[]
  total: number
}

function queryString(query?: ReportListQuery) {
  const params = new URLSearchParams()
  Object.entries(query || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null) params.set(key, String(value))
  })
  const text = params.toString()
  return text ? `?${text}` : ''
}

export async function listReportsPage(query?: ReportListQuery) {
  return http.get<ReportListResult>(`/reports${queryString(query)}`)
}

export async function listReports(query?: ReportListQuery) {
  const response = await listReportsPage(query)
  return response.reports
}

export async function generateReport(payload: ReportGeneratePayload) {
  const response = await http.post<{ report: Report }>('/reports', payload)
  return response.report
}

export async function getReport(reportId: string) {
  const response = await http.get<{ report: Report }>(`/reports/${reportId}`)
  return response.report
}

export async function updateReport(reportId: string, payload: ReportUpdatePayload) {
  const response = await http.patch<{ report: Report }>(`/reports/${reportId}`, payload)
  return response.report
}

export async function deleteReport(reportId: string, deleteStorage = false) {
  return http.delete<{ message: string }>(`/reports/${reportId}?delete_storage=${deleteStorage}`)
}

export function downloadReport(reportId: string) {
  return downloadApiFile(`/reports/${reportId}/download`, `report-${reportId}.md`)
}
