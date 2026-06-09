<script setup lang="ts">
defineProps<{
  title?: string
  description?: string
  compact?: boolean
}>()
</script>

<template>
  <section class="surface base-section" :class="{ compact }">
    <header v-if="title || description || $slots.actions" class="base-section-head">
      <div>
        <h2 v-if="title">{{ title }}</h2>
        <p v-if="description">{{ description }}</p>
      </div>
      <div v-if="$slots.actions" class="base-section-actions">
        <slot name="actions" />
      </div>
    </header>
    <slot />
  </section>
</template>

<style scoped>
.base-section {
  position: relative;
  overflow: hidden;
  border-radius: var(--radius);
  padding: 20px;
}

.base-section.compact {
  padding: 16px;
}

.base-section::before {
  content: "";
  position: absolute;
  inset: 0 0 auto;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.95), transparent);
  pointer-events: none;
}

.base-section-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid rgba(215, 224, 234, 0.7);
}

.base-section-head h2 {
  margin: 0 0 6px;
  font-size: 20px;
  line-height: 1.25;
}

.base-section-head p {
  margin: 0;
  color: var(--muted-foreground);
  line-height: 1.6;
}

.base-section-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  justify-content: flex-end;
}

@media (max-width: 920px) {
  .base-section-head {
    display: grid;
  }

  .base-section-actions {
    justify-content: flex-start;
  }
}
</style>
