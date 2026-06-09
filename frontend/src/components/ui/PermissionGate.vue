<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from '../../composables/useI18n'
import { usePermissions } from '../../composables/usePermissions'
import { areaLabel, roleLabel, type PermissionArea } from '../../lib/permissions'

const props = defineProps<{
  area: PermissionArea
  compact?: boolean
}>()

const { canUse, user } = usePermissions()
const { t } = useI18n()
const allowed = computed(() => canUse(props.area))
const deniedMessage = computed(() =>
  t('permission.deniedMessage', {
    role: roleLabel(user.value?.role),
    area: areaLabel(props.area),
  }),
)
</script>

<template>
  <slot v-if="allowed" />
  <div v-else class="permission-note" :class="{ compact }">
    <strong>{{ t('permission.deniedTitle') }}</strong>
    <p>{{ deniedMessage }}</p>
  </div>
</template>

<style scoped>
.permission-note {
  display: grid;
  gap: 6px;
  padding: 14px;
  border: 1px dashed rgba(148, 163, 184, 0.76);
  border-radius: var(--radius);
  background: rgba(248, 250, 252, 0.72);
  color: #475569;
}

.permission-note.compact {
  padding: 10px 12px;
}

.permission-note strong {
  color: var(--foreground);
  font-size: 14px;
}

.permission-note p {
  margin: 0;
  line-height: 1.55;
  font-size: 13px;
}
</style>
