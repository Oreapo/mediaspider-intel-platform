import { computed } from 'vue'
import { useAuth } from './useAuth'
import { canUse, hasRole, type AppRole, type PermissionArea } from '../lib/permissions'

export function usePermissions() {
  const { user } = useAuth()

  return {
    user,
    canAnalyze: computed(() => canUse(user.value, 'analysis')),
    canOperate: computed(() => canUse(user.value, 'operations')),
    canUseWorkflow: computed(() => canUse(user.value, 'workflow')),
    canUse: (area: PermissionArea) => canUse(user.value, area),
    hasRole: (roles: AppRole[]) => hasRole(user.value, roles),
  }
}
