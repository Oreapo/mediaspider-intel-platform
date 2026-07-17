<script setup lang="ts">
import { useI18n } from '../../composables/useI18n'
import { useTheme } from '../../composables/useTheme'

// `icon` is kept for call-site compatibility; the emblem is now the brand mascot.
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
const { theme } = useTheme()
</script>

<template>
  <div class="empty-state">
    <img
      class="empty-mascot"
      :src="theme === 'pink' ? '/brand/mascot-pink.png' : '/brand/mascot-blue.png'"
      alt=""
      aria-hidden="true"
    />
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

.empty-mascot {
  flex-shrink: 0;
  width: 84px;
  height: auto;
  filter: drop-shadow(0 8px 16px color-mix(in oklch, var(--primary) 18%, transparent));
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
