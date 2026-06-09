<script setup lang="ts">
withDefaults(
  defineProps<{
    tone?: 'success' | 'error' | 'info' | 'warning'
    title?: string
    message: string
  }>(),
  {
    tone: 'info',
  },
)
</script>

<template>
  <div class="app-alert" :class="tone" role="status">
    <span class="alert-mark" aria-hidden="true" />
    <div>
      <strong v-if="title">{{ title }}</strong>
      <p>{{ message }}</p>
    </div>
  </div>
</template>

<style scoped>
.app-alert {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  align-items: start;
  padding: 13px 14px;
  border: 1px solid rgba(190, 202, 216, 0.82);
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.82);
  box-shadow: var(--shadow-subtle);
}

.alert-mark {
  width: 10px;
  height: 10px;
  margin-top: 5px;
  border-radius: 3px;
  background: var(--primary);
  box-shadow: 0 0 0 4px color-mix(in oklch, var(--primary) 14%, transparent);
}

.app-alert strong {
  display: block;
  margin-bottom: 3px;
  color: var(--foreground);
  font-size: 14px;
}

.app-alert p {
  margin: 0;
  color: #475569;
  line-height: 1.55;
  overflow-wrap: anywhere;
}

.app-alert.success {
  border-color: rgba(22, 163, 74, 0.24);
  background: rgba(240, 253, 244, 0.86);
}

.app-alert.success .alert-mark {
  background: #16a34a;
  box-shadow: 0 0 0 4px rgba(22, 163, 74, 0.12);
}

.app-alert.error {
  border-color: rgba(220, 38, 38, 0.24);
  background: rgba(254, 242, 242, 0.9);
}

.app-alert.error .alert-mark {
  background: #dc2626;
  box-shadow: 0 0 0 4px rgba(220, 38, 38, 0.12);
}

.app-alert.warning {
  border-color: rgba(217, 119, 6, 0.28);
  background: rgba(255, 251, 235, 0.9);
}

.app-alert.warning .alert-mark {
  background: #d97706;
  box-shadow: 0 0 0 4px rgba(217, 119, 6, 0.14);
}
</style>
