<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from '../../composables/useI18n'

const props = withDefaults(
  defineProps<{
    title?: string
    rows?: number
  }>(),
  {
    rows: 3,
  },
)

const { t } = useI18n()
const displayTitle = computed(() => props.title || t('common.loading'))
</script>

<template>
  <div class="loading-state" role="status" aria-live="polite">
    <div class="loading-head">
      <span class="spinner" aria-hidden="true" />
      <strong>{{ displayTitle }}</strong>
    </div>
    <div class="skeleton-list" aria-hidden="true">
      <span v-for="index in rows" :key="index" class="skeleton-row" />
    </div>
  </div>
</template>

<style scoped>
.loading-state {
  display: grid;
  gap: 14px;
  padding: 16px;
  border: 1px solid rgba(215, 224, 234, 0.78);
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.72);
}

.loading-head {
  display: flex;
  gap: 10px;
  align-items: center;
  color: var(--foreground);
  font-weight: 800;
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid color-mix(in oklch, var(--primary) 18%, white);
  border-top-color: var(--primary);
  border-radius: 999px;
  animation: spin 850ms linear infinite;
}

.skeleton-list {
  display: grid;
  gap: 8px;
}

.skeleton-row {
  height: 13px;
  border-radius: 4px;
  background:
    linear-gradient(90deg, rgba(226, 232, 240, 0.72), rgba(255, 255, 255, 0.94), rgba(226, 232, 240, 0.72));
  background-size: 220% 100%;
  animation: shimmer 1100ms ease-in-out infinite;
}

.skeleton-row:nth-child(2) {
  width: 78%;
}

.skeleton-row:nth-child(3) {
  width: 58%;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes shimmer {
  0% {
    background-position: 120% 0;
  }

  100% {
    background-position: -120% 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .spinner,
  .skeleton-row {
    animation: none;
  }
}
</style>
