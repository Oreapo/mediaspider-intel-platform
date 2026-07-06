<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from '../../composables/useI18n'

const props = defineProps<{
  title?: string
  message: string
  retryLabel?: string
  secondaryLabel?: string
}>()

defineEmits<{
  retry: []
  secondary: []
}>()

const { t } = useI18n()
const displayTitle = computed(() => props.title || t('common.loadFailed'))
const displayRetryLabel = computed(() => props.retryLabel || t('common.retry'))
</script>

<template>
  <div class="retry-state" role="alert">
    <div class="retry-copy">
      <span class="retry-mark" aria-hidden="true" />
      <div>
        <strong>{{ displayTitle }}</strong>
        <p>{{ message }}</p>
      </div>
    </div>
    <div class="retry-actions">
      <button class="primary-button" type="button" @click="$emit('retry')">
        {{ displayRetryLabel }}
      </button>
      <button v-if="secondaryLabel" class="secondary-button" type="button" @click="$emit('secondary')">
        {{ secondaryLabel }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.retry-state {
  display: grid;
  gap: 16px;
  padding: 18px;
  border: 1px solid rgba(220, 38, 38, 0.24);
  border-radius: var(--radius);
  background:
    linear-gradient(135deg, rgba(254, 242, 242, 0.92), rgba(255, 255, 255, 0.86)),
    var(--card);
}

.retry-copy {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}

.retry-mark {
  width: 12px;
  height: 12px;
  margin-top: 5px;
  border-radius: 3px;
  background: #dc2626;
  box-shadow: 0 0 0 4px rgba(220, 38, 38, 0.12);
}

.retry-copy strong {
  display: block;
  margin-bottom: 4px;
  color: var(--foreground);
}

.retry-copy p {
  margin: 0;
  color: #475569;
  line-height: 1.55;
  overflow-wrap: anywhere;
}

.retry-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.primary-button,
.secondary-button {
  border: none;
  border-radius: var(--radius);
  padding: 10px 14px;
  font-weight: 800;
  cursor: pointer;
}

.primary-button {
  color: white;
  background: linear-gradient(135deg, var(--primary-strong), var(--primary));
}

.secondary-button {
  color: #1e293b;
  border: 1px solid rgba(190, 202, 216, 0.82);
  background: rgba(248, 250, 252, 0.94);
}
</style>
