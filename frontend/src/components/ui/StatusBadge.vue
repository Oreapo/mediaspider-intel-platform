<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    label: string
    tone?: string
  }>(),
  {
    tone: 'neutral',
  },
)

void props
</script>

<template>
  <span class="status-badge" :class="tone">{{ label }}</span>
</template>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  min-height: 28px;
  padding: 6px 10px;
  border-radius: var(--radius);
  border: 1px solid transparent;
  font-size: 12px;
  font-weight: 800;
  line-height: 1;
  text-transform: uppercase;
  white-space: nowrap;
}

.status-badge.neutral {
  border-color: rgba(148, 163, 184, 0.26);
  background: rgba(241, 245, 249, 0.78);
  color: #475569;
}

.status-badge.info {
  border-color: color-mix(in oklch, var(--primary) 24%, white);
  background: color-mix(in oklch, var(--primary) 9%, white);
  color: var(--primary);
}

.status-badge.success {
  border-color: rgba(22, 163, 74, 0.22);
  background: rgba(220, 252, 231, 0.74);
  color: #15803d;
}

.status-badge.warning {
  border-color: rgba(217, 119, 6, 0.24);
  background: rgba(254, 243, 199, 0.78);
  color: #a16207;
}

.status-badge.danger {
  border-color: rgba(220, 38, 38, 0.22);
  background: rgba(254, 226, 226, 0.74);
  color: #b91c1c;
}
</style>
