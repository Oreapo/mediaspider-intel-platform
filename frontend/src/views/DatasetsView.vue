<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { createDataset, deleteDataset, previewDataset } from '../api/datasets'
import AppAlert from '../components/ui/AppAlert.vue'
import AppSelect from '../components/ui/AppSelect.vue'
import PlatformLogo from '../components/ui/PlatformLogo.vue'
import BaseSection from '../components/ui/BaseSection.vue'
import EmptyState from '../components/ui/EmptyState.vue'
import FieldError from '../components/ui/FieldError.vue'
import LoadingState from '../components/ui/LoadingState.vue'
import PaginationBar from '../components/ui/PaginationBar.vue'
import PermissionGate from '../components/ui/PermissionGate.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import { useDatasets } from '../composables/useDatasets'
import { useI18n } from '../composables/useI18n'
import { enumLabel as labelValue, scenarioLabel } from '../composables/useEnumLabel'
import { usePlatformModels } from '../composables/usePlatformModels'
import { requestConfirm } from '../lib/confirm'
import { lastPageOffset } from '../lib/pagination'
import { required, type ValidationErrors } from '../lib/validation'
import type { DatasetPreview } from '../types'

const {
  items: datasetItems,
  total: datasetTotal,
  isLoading: datasetsLoading,
  error: datasetsError,
  fetchItems: fetchDatasets,
} = useDatasets()
const { items: platformItems } = usePlatformModels()
const { t } = useI18n()

const form = ref({
  dataset_name: '',
  dataset_type: 'raw',
  source_platform: 'xhs',
  scenario_type: 'lead_diversion',
  storage_uri: '',
  tags: '',
})
const filters = ref({
  q: '',
  source_platform: '',
  dataset_type: '',
  scenario_type: '',
  tag: '',
  limit: 100,
  offset: 0,
})
const preview = ref<DatasetPreview | null>(null)
const selectedDatasetId = ref('')
const creating = ref(false)
const message = ref('')
const error = ref('')
const formErrors = ref<ValidationErrors>({})

// Drill-down from the dashboard platform comparison: /datasets?platform=xhs
const route = useRoute()
if (typeof route.query.platform === 'string' && route.query.platform) {
  filters.value.source_platform = route.query.platform
}
onMounted(() => {
  if (filters.value.source_platform) void fetchDatasetPage()
})

const scenarioOptions = computed(() => [
  { value: 'lead_diversion', label: t('scenario.lead_diversion') },
  { value: 'gray_recruitment', label: t('scenario.gray_recruitment') },
  { value: 'fraud_promotion', label: t('scenario.fraud_promotion') },
  { value: 'seller_risk', label: t('scenario.seller_risk') },
  { value: 'product_risk', label: t('scenario.product_risk') },
  { value: 'topic_watch', label: t('scenario.topic_watch') },
])

const selectedDataset = computed(() =>
  datasetItems.value.find((item) => item.id === selectedDatasetId.value),
)

const datasetTypes = computed(() => Array.from(new Set(datasetItems.value.map((item) => item.dataset_type))).sort())

function parseTags(text: string) {
  return text
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function validateDatasetForm() {
  const errors: ValidationErrors = {}
  const nameError = required(form.value.dataset_name, t('datasets.name'))

  if (nameError) errors.dataset_name = nameError
  formErrors.value = errors
  return Object.keys(errors).length === 0
}

async function submitDataset() {
  message.value = ''
  error.value = ''
  if (!validateDatasetForm()) {
    error.value = t('datasets.fixFormErrors')
    return
  }

  creating.value = true
  try {
    await createDataset({
      dataset_name: form.value.dataset_name,
      dataset_type: form.value.dataset_type,
      source_platform: form.value.source_platform,
      scenario_type: form.value.scenario_type,
      storage_uri: form.value.storage_uri,
      tags: parseTags(form.value.tags),
    })
    message.value = t('datasets.createdMessage')
    form.value.dataset_name = ''
    form.value.storage_uri = ''
    form.value.tags = ''
    await fetchDatasetPage()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    creating.value = false
  }
}

async function applyFilters() {
  selectedDatasetId.value = ''
  preview.value = null
  filters.value.offset = 0
  await fetchDatasetPage()
}

async function fetchDatasetPage() {
  await fetchDatasets({
    q: filters.value.q,
    source_platform: filters.value.source_platform,
    dataset_type: filters.value.dataset_type,
    scenario_type: filters.value.scenario_type,
    tag: filters.value.tag,
    limit: filters.value.limit,
    offset: filters.value.offset,
  })
  const normalizedOffset = lastPageOffset(datasetTotal.value, filters.value.limit)
  if (filters.value.offset > normalizedOffset) {
    filters.value.offset = normalizedOffset
    if (datasetTotal.value > 0) await fetchDatasetPage()
  }
}

async function changeDatasetPage(offset: number) {
  selectedDatasetId.value = ''
  preview.value = null
  filters.value.offset = offset
  await fetchDatasetPage()
}

async function clearFilters() {
  filters.value = {
    q: '',
    source_platform: '',
    dataset_type: '',
    scenario_type: '',
    tag: '',
    limit: 100,
    offset: 0,
  }
  await applyFilters()
}

async function loadPreview(datasetId: string) {
  selectedDatasetId.value = datasetId
  message.value = ''
  error.value = ''
  try {
    preview.value = await previewDataset(datasetId, 20)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
    preview.value = null
  }
}

async function removeDataset(datasetId: string) {
  const confirmed = await requestConfirm({
    title: t('datasets.deleteTitle'),
    message: t('datasets.deleteMessage'),
    confirmLabel: t('datasets.deleteConfirm'),
  })
  if (!confirmed) return

  message.value = ''
  error.value = ''
  try {
    await deleteDataset(datasetId)
    message.value = t('datasets.deletedMessage')
    if (selectedDatasetId.value === datasetId) {
      selectedDatasetId.value = ''
      preview.value = null
    }
    await fetchDatasetPage()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

function datasetTypeLabel(value: string) {
  const key = `datasetType.${value}`
  const translated = t(key)
  return translated === key ? value : translated
}
</script>

<template>
  <section class="page-grid">
    <div class="dataset-workspace">
      <aside class="dataset-side-panel">
    <BaseSection compact :title="t('datasets.createTitle')" :description="t('datasets.createDescription')">
      <PermissionGate area="workflow">
      <form class="dataset-form" @submit.prevent="submitDataset">
        <div class="grid-two">
          <label class="field">
            <span>{{ t('datasets.name') }}</span>
            <input v-model="form.dataset_name" required :placeholder="t('datasets.namePlaceholder')" />
            <FieldError :message="formErrors.dataset_name" />
          </label>

          <label class="field">
            <span>{{ t('datasets.sourcePlatform') }}</span>
            <AppSelect
              v-model="form.source_platform"
              :options="platformItems.map((item) => ({
                value: item.platform,
                label: labelValue(item.platform),
                platform: item.platform,
              }))"
            />
          </label>
        </div>

        <div class="grid-two">
          <label class="field">
            <span>{{ t('datasets.type') }}</span>
            <AppSelect
              v-model="form.dataset_type"
              :options="[
                { value: 'raw', label: t('datasetType.raw') },
                { value: 'normalized', label: t('datasetType.normalized') },
                { value: 'analysis_ready', label: t('datasetType.analysis_ready') },
              ]"
            />
          </label>

          <label class="field">
            <span>{{ t('tasks.scenario') }}</span>
            <AppSelect v-model="form.scenario_type" :options="scenarioOptions" />
          </label>
        </div>

        <div class="grid-two">
          <label class="field">
            <span>{{ t('datasets.tags') }}</span>
            <input v-model="form.tags" placeholder="brand, campaign, launch" />
          </label>
          <div class="field field-empty" aria-hidden="true" />
        </div>

        <label class="field">
          <span>{{ t('datasets.storageUri') }}</span>
          <input
            v-model="form.storage_uri"
            :placeholder="t('datasets.storagePlaceholder')"
          />
        </label>

        <div class="actions">
          <button class="primary-button" :disabled="creating" type="submit">
            {{ creating ? t('datasets.creating') : t('datasets.create') }}
          </button>
        </div>
        <AppAlert v-if="message" tone="success" :title="t('tasks.successTitle')" :message="message" />
        <AppAlert v-if="error" tone="error" :title="t('tasks.actionFailedTitle')" :message="error" />
      </form>
      </PermissionGate>
    </BaseSection>
      </aside>

      <main class="dataset-main-panel">
    <div class="split-grid">
      <BaseSection :title="t('datasets.listTitle')" :description="t('datasets.listDescription')">
        <form class="filter-form" @submit.prevent="applyFilters">
          <label class="field">
            <span>{{ t('tasks.search') }}</span>
            <input v-model="filters.q" :placeholder="t('datasets.searchPlaceholder')" />
          </label>

          <label class="field">
            <span>{{ t('tasks.platform') }}</span>
            <AppSelect
              v-model="filters.source_platform"
              :options="[
                { value: '', label: t('tasks.allPlatforms') },
                ...platformItems.map((item) => ({ value: item.platform, label: labelValue(item.platform), platform: item.platform })),
              ]"
            />
          </label>

          <label class="field">
            <span>{{ t('datasets.type') }}</span>
            <AppSelect
              v-model="filters.dataset_type"
              :options="[
                { value: '', label: t('datasets.allTypes') },
                ...datasetTypes.map((item) => ({ value: item, label: datasetTypeLabel(item) })),
              ]"
            />
          </label>

          <label class="field">
            <span>{{ t('tasks.scenario') }}</span>
            <AppSelect
              v-model="filters.scenario_type"
              :options="[{ value: '', label: t('tasks.allScenarios') }, ...scenarioOptions]"
            />
          </label>

          <label class="field">
            <span>{{ t('datasets.tags') }}</span>
            <input v-model="filters.tag" placeholder="spring" />
          </label>

          <label class="field">
            <span>{{ t('tasks.limit') }}</span>
            <input v-model.number="filters.limit" min="1" max="500" step="1" type="number" />
          </label>

          <div class="actions filter-actions">
            <button class="primary-button" :disabled="datasetsLoading" type="submit">{{ t('tasks.apply') }}</button>
            <button class="secondary-button" :disabled="datasetsLoading" type="button" @click="clearFilters">{{ t('tasks.clear') }}</button>
          </div>
        </form>

        <LoadingState v-if="datasetsLoading" :title="t('datasets.loading')" />
        <AppAlert v-else-if="datasetsError" tone="error" :title="t('common.loadFailed')" :message="datasetsError" />
        <div v-else class="dataset-list">
          <article v-for="item in datasetItems" :key="item.id" class="dataset-item">
            <div class="dataset-main">
              <div>
                <strong>{{ item.dataset_name }}</strong>
                <p class="platform-line">
                  <PlatformLogo :platform="item.source_platform" :size="16" />
                  {{ labelValue(item.source_platform) }} · {{ scenarioLabel(item.scenario_type) }} ·
                  {{ datasetTypeLabel(item.dataset_type) }} ·
                  {{ t('datasets.recordCount', { count: item.record_count }) }}
                </p>
              </div>
              <StatusBadge :label="datasetTypeLabel(item.dataset_type)" tone="info" />
            </div>
            <div class="dataset-meta">
              <span>{{ item.storage_uri || t('datasets.noStorage') }}</span>
              <code>{{ item.id }}</code>
            </div>
            <div class="actions">
              <RouterLink class="secondary-button link-button" :to="{ name: 'dataset-detail', params: { datasetId: item.id } }">
                {{ t('datasets.viewDetail') }}
              </RouterLink>
              <button class="secondary-button" type="button" @click="loadPreview(item.id)">{{ t('datasets.preview') }}</button>
              <PermissionGate area="workflow" compact>
              <button class="secondary-button destructive" type="button" @click="removeDataset(item.id)">
                {{ t('datasets.delete') }}
              </button>
              </PermissionGate>
            </div>
          </article>
          <EmptyState v-if="!datasetItems.length" :title="t('datasets.emptyTitle')" :description="t('datasets.emptyDescription')" />
          <PaginationBar
            :total="datasetTotal"
            :limit="filters.limit"
            :offset="filters.offset"
            :loading="datasetsLoading"
            @change="changeDatasetPage"
          />
        </div>
      </BaseSection>

      <BaseSection :title="t('datasets.previewTitle')" :description="selectedDataset ? selectedDataset.dataset_name : t('datasets.previewDescription')">
        <div v-if="preview?.columns.length" class="preview-wrap">
          <table class="preview-table">
            <thead>
              <tr>
                <th v-for="column in preview.columns" :key="column">{{ column }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, rowIndex) in preview.rows" :key="rowIndex">
                <td v-for="(cell, cellIndex) in row" :key="cellIndex">{{ cell }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <EmptyState v-else :title="t('datasets.previewEmptyTitle')" :description="t('datasets.previewEmptyDescription')" />
      </BaseSection>
    </div>
      </main>
    </div>
  </section>
</template>

<style scoped>
.page-grid,
.dataset-form,
.dataset-list,
.filter-form {
  display: grid;
  gap: 18px;
}

.dataset-workspace {
  display: grid;
  grid-template-columns: minmax(300px, 360px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.dataset-side-panel {
  position: sticky;
  top: 86px;
  max-height: calc(100vh - 104px);
  min-width: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding-right: 2px;
}

.dataset-main-panel {
  min-width: 0;
}

.dataset-side-panel .grid-two {
  grid-template-columns: 1fr;
}

.dataset-side-panel .field-empty {
  display: none;
}

.dataset-side-panel .actions {
  display: grid;
}

.dataset-side-panel .primary-button {
  width: 100%;
}

.split-grid {
  display: grid;
  grid-template-columns: 1.1fr 1fr;
  gap: 18px;
}

.section-card {
  border-radius: 24px;
  padding: 22px;
}

.section-head {
  margin-bottom: 16px;
}

.section-head h2 {
  margin: 0 0 6px;
}

.section-head p,
.muted,
.field span,
.dataset-meta,
.dataset-item p {
  color: #64748b;
}

.grid-two {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  margin-bottom: 18px;
}

.filter-form .field {
  flex: 1 1 158px;
  min-width: 150px;
}

.field {
  display: grid;
  gap: 8px;
}

.field span {
  font-size: 13px;
  font-weight: 700;
}

.field input,
.field select {
  width: 100%;
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid rgba(203, 213, 225, 0.95);
  background: rgba(255, 255, 255, 0.94);
}

.platform-line {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.dataset-item {
  padding: 16px;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(248, 250, 252, 0.82);
}

.dataset-main {
  display: flex;
  gap: 12px;
  justify-content: space-between;
}

.dataset-main strong {
  display: block;
  margin-bottom: 4px;
}

.dataset-main p {
  margin: 0;
}

.dataset-meta {
  margin: 10px 0 12px;
  font-size: 13px;
}

.dataset-id {
  font-size: 12px;
  color: #2563eb;
  font-weight: 700;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.filter-actions {
  flex-wrap: nowrap;
}

.primary-button,
.secondary-button {
  border: none;
  border-radius: 12px;
  padding: 10px 14px;
  font-weight: 700;
  cursor: pointer;
}

.primary-button {
  background: linear-gradient(135deg, #2563eb 0%, var(--primary) 100%);
  color: white;
}

.secondary-button {
  background: rgba(226, 232, 240, 0.9);
  color: #1e293b;
}

.link-button {
  display: inline-flex;
  align-items: center;
  text-decoration: none;
}

.secondary-button.destructive {
  background: rgba(254, 226, 226, 0.95);
  color: #b91c1c;
}

.preview-wrap {
  overflow: auto;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.9);
}

.preview-table {
  width: 100%;
  min-width: 640px;
  border-collapse: collapse;
}

.preview-table th,
.preview-table td {
  padding: 10px 12px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.8);
  text-align: left;
  vertical-align: top;
}

.preview-table th {
  background: rgba(241, 245, 249, 0.92);
  font-size: 13px;
}

.success-text {
  color: #15803d;
}

.error-text {
  color: #dc2626;
}

@media (max-width: 980px) {
  .dataset-workspace {
    grid-template-columns: 1fr;
  }

  .dataset-side-panel {
    position: static;
    max-height: none;
    overflow: visible;
    padding-right: 0;
  }

  .split-grid,
  .grid-two,
  .filter-form {
    grid-template-columns: 1fr;
  }
}
</style>
