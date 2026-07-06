<script setup lang="ts">
import AppIcon from './AppIcon.vue'
import { useI18n } from '../../composables/useI18n'

withDefaults(
  defineProps<{
    title?: string
    description?: string
    icon?: string
  }>(),
  {
    icon: 'layers',
  },
)

const { t } = useI18n()
</script>

<template>
  <div class="empty-state">
    <div class="empty-mark" aria-hidden="true">
      <AppIcon :name="icon" :size="22" />
    </div>
    <div class="empty-copy">
      <strong>{{ title || t('common.noData') }}</strong>
      <p v-if="description">{{ description }}</p>
    </div>
    <div v-if="$slots.default" class="empty-actions">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.empty-state {
  min-height: 128px;
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: center;
  padding: 22px;
  border: 1px solid color-mix(in oklch, var(--primary) 10%, var(--border));
  border-radius: var(--radius);
  background:
    radial-gradient(120% 140% at 0% 0%, color-mix(in oklch, var(--primary) 5%, transparent), transparent 60%),
    linear-gradient(135deg, rgba(255, 255, 255, 0.9), rgba(248, 250, 252, 0.74)),
    var(--card);
  color: var(--muted-foreground);
}

.empty-mark {
  flex-shrink: 0;
  width: 46px;
  height: 46px;
  display: grid;
  place-items: center;
  border-radius: 14px;
  color: var(--primary);
  border: 1px solid color-mix(in oklch, var(--primary) 22%, transparent);
  background: color-mix(in oklch, var(--primary) 9%, white);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.7),
    0 8px 18px -12px var(--brand-glow);
}

.empty-copy {
  flex: 1;
  min-width: 180px;
}

.empty-copy strong {
  display: block;
  color: var(--foreground);
  font-size: 15px;
  letter-spacing: -0.01em;
}

.empty-copy p {
  margin: 5px 0 0;
  line-height: 1.55;
  font-size: 13px;
}

.empty-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
