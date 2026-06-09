<script setup lang="ts">
defineProps<{
  title?: string
  description?: string
}>()
</script>

<template>
  <div class="empty-state">
    <div class="empty-mark" aria-hidden="true">
      <span />
    </div>
    <div>
      <strong>{{ title || '暂无数据' }}</strong>
      <p v-if="description">{{ description }}</p>
    </div>
  </div>
</template>

<style scoped>
.empty-state {
  min-height: 116px;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 14px;
  align-items: center;
  padding: 18px;
  border: 1px dashed rgba(148, 163, 184, 0.58);
  border-radius: var(--radius);
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.84), rgba(248, 250, 252, 0.72)),
    var(--card);
  color: var(--muted-foreground);
}

.empty-mark {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border-radius: var(--radius);
  border: 1px solid rgba(190, 202, 216, 0.78);
  background: rgba(255, 255, 255, 0.78);
}

.empty-mark span {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  border: 2px solid color-mix(in oklch, var(--primary) 54%, white);
  box-shadow: 8px 8px 0 color-mix(in oklch, var(--accent) 26%, white);
}

.empty-state strong {
  display: block;
  color: var(--foreground);
  font-size: 15px;
}

.empty-state p {
  margin: 4px 0 0;
  line-height: 1.55;
}
</style>
