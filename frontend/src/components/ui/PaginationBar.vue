<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from '../../composables/useI18n'

const props = withDefaults(
  defineProps<{
    total: number
    limit: number
    offset: number
    loading?: boolean
  }>(),
  {
    loading: false,
  },
)

const emit = defineEmits<{
  change: [offset: number]
}>()

const { t } = useI18n()

const safeLimit = computed(() => Math.max(1, props.limit))
const pageCount = computed(() => Math.max(1, Math.ceil(props.total / safeLimit.value)))
const currentPage = computed(() =>
  Math.min(pageCount.value, Math.floor(Math.max(0, props.offset) / safeLimit.value) + 1),
)
const firstItem = computed(() => (props.total ? props.offset + 1 : 0))
const lastItem = computed(() => Math.min(props.offset + safeLimit.value, props.total))
const canGoBack = computed(() => props.offset > 0 && !props.loading)
const canGoForward = computed(() => props.offset + safeLimit.value < props.total && !props.loading)

function goToPage(page: number) {
  const normalizedPage = Math.min(Math.max(page, 1), pageCount.value)
  emit('change', (normalizedPage - 1) * safeLimit.value)
}
</script>

<template>
  <nav v-if="total > 0" class="pagination-bar" :aria-label="t('common.pagination')">
    <p>
      {{
        t('common.paginationSummary', {
          start: firstItem,
          end: lastItem,
          total,
          page: currentPage,
          pages: pageCount,
        })
      }}
    </p>
    <div class="pagination-actions">
      <button
        class="pagination-button"
        type="button"
        :disabled="!canGoBack"
        :aria-label="t('common.firstPage')"
        :title="t('common.firstPage')"
        @click="goToPage(1)"
      >
        «
      </button>
      <button
        class="pagination-button"
        type="button"
        :disabled="!canGoBack"
        :aria-label="t('common.previousPage')"
        :title="t('common.previousPage')"
        @click="goToPage(currentPage - 1)"
      >
        ‹
      </button>
      <span class="page-indicator" aria-live="polite">{{ currentPage }} / {{ pageCount }}</span>
      <button
        class="pagination-button"
        type="button"
        :disabled="!canGoForward"
        :aria-label="t('common.nextPage')"
        :title="t('common.nextPage')"
        @click="goToPage(currentPage + 1)"
      >
        ›
      </button>
      <button
        class="pagination-button"
        type="button"
        :disabled="!canGoForward"
        :aria-label="t('common.lastPage')"
        :title="t('common.lastPage')"
        @click="goToPage(pageCount)"
      >
        »
      </button>
    </div>
  </nav>
</template>

<style scoped>
.pagination-bar {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-top: 14px;
  border-top: 1px solid rgba(215, 224, 234, 0.82);
}

.pagination-bar p {
  min-width: 0;
  margin: 0;
  color: var(--muted-foreground);
  font-size: 13px;
  line-height: 1.5;
}

.pagination-actions {
  display: grid;
  grid-template-columns: repeat(2, 36px) minmax(64px, auto) repeat(2, 36px);
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
}

.pagination-button {
  width: 36px;
  height: 36px;
  padding: 0;
  display: inline-grid;
  place-items: center;
  border: 1px solid rgba(190, 202, 216, 0.82);
  border-radius: var(--radius);
  background: rgba(248, 250, 252, 0.94);
  color: var(--foreground);
  font-size: 20px;
  line-height: 1;
}

.pagination-button:not(:disabled):hover {
  border-color: color-mix(in oklch, var(--primary) 46%, white);
  background: white;
  box-shadow: var(--shadow-subtle);
}

.page-indicator {
  min-width: 64px;
  text-align: center;
  color: var(--foreground);
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
}

@media (max-width: 620px) {
  .pagination-bar {
    align-items: stretch;
    flex-direction: column;
  }

  .pagination-actions {
    justify-content: space-between;
  }
}
</style>
