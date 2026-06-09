import type { AuthUser } from '../types'
import { translate } from '../composables/useI18n'

export type AppRole = 'admin' | 'analyst' | 'operator' | 'viewer'
export type PermissionArea = 'analysis' | 'operations' | 'workflow'

const permissionRoles: Record<PermissionArea, AppRole[]> = {
  analysis: ['admin', 'analyst'],
  operations: ['admin', 'operator'],
  workflow: ['admin', 'analyst', 'operator'],
}

export function hasRole(user: AuthUser | null, roles: AppRole[]) {
  if (!user) return false
  if (user.role === 'admin') return true
  return roles.includes(user.role as AppRole)
}

export function canUse(user: AuthUser | null, area: PermissionArea) {
  return hasRole(user, permissionRoles[area])
}

export function roleLabel(role?: string) {
  const labelKeys: Record<string, string> = {
    admin: 'role.admin',
    analyst: 'role.analyst',
    operator: 'role.operator',
    viewer: 'role.viewer',
  }
  const labelKey = labelKeys[role || '']
  return labelKey ? translate(labelKey) : role || translate('role.unknown')
}

export function areaLabel(area: PermissionArea) {
  const labelKeys: Record<PermissionArea, string> = {
    analysis: 'permission.analysis',
    operations: 'permission.operations',
    workflow: 'permission.workflow',
  }
  return translate(labelKeys[area])
}
