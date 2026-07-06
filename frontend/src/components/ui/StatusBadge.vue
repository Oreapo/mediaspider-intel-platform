<script setup lang="ts">
type Tone = 'neutral' | 'info' | 'success' | 'warning' | 'danger'

withDefaults(
  defineProps<{
    label: string
    tone?: Tone | string
    dot?: boolean
  }>(),
  {
    tone: 'neutral',
    dot: true,
  },
)
</script>

<template>
  <span class="status-badge" :class="tone">
    <span v-if="dot" class="badge-dot" aria-hidden="true" />
    <span class="badge-label">{{ label }}</span>
  </span>
</template>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  width: fit-content;
  min-height: 26px;
  padding: 4px 11px 4px 9px;
  border-radius: 999px;
  border: 1px solid transparent;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: 0.01em;
  white-space: nowrap;
}

.badge-dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: currentColor;
  box-shadow: 0 0 0 3px color-mix(in oklch, currentColor 18%, transparent);
}

.badge-label {
  color: color-mix(in oklch, currentColor 82%, #1b2440);
}

.status-badge.neutral {
  border-color: rgba(148, 163, 184, 0.3);
  background: rgba(241, 245, 249, 0.72);
  color: #64748b;
}

.status-badge.info {
  border-color: color-mix(in oklch, var(--primary) 24%, transparent);
  background: color-mix(in oklch, var(--primary) 8%, white);
  color: var(--primary);
}

.status-badge.success {
  border-color: color-mix(in oklch, var(--success) 30%, transparent);
  background: color-mix(in oklch, var(--success) 10%, white);
  color: var(--success);
}

.status-badge.warning {
  border-color: color-mix(in oklch, var(--warning) 32%, transparent);
  background: color-mix(in oklch, var(--warning) 12%, white);
  color: var(--warning);
}

.status-badge.danger {
  border-color: color-mix(in oklch, var(--destructive) 30%, transparent);
  background: color-mix(in oklch, var(--destructive) 10%, white);
  color: var(--destructive);
}
</style>
