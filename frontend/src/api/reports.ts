import { apiDownloadUrl, http } from '../lib/http'
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

export async function listReports() {
  const response = await http.get<{ reports: Report[] }>('/reports')
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

export function reportDownloadUrl(reportId: string) {
  return apiDownloadUrl(`/reports/${reportId}/download`)
}
