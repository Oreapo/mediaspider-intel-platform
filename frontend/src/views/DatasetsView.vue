<script setup lang="ts">
import { computed, ref } from 'vue'
import { createDataset, deleteDataset, previewDataset } from '../api/datasets'
import { useDatasets } from '../composables/useDatasets'
import { usePlatformModels } from '../composables/usePlatformModels'
import type { DatasetPreview } from '../types'

const {
  items: datasetItems,
  isLoading: datasetsLoading,
  error: datasetsError,
  fetchItems: fetchDatasets,
} = useDatasets()
const { items: platformItems } = usePlatformModels()

const form = ref({
  dataset_name: '',
  dataset_type: 'raw',
  source_platform: 'xhs',
  scenario_type: 'lead_diversion',
  storage_uri: '',
  tags: '',
})
const preview = ref<DatasetPreview | null>(null)
const selectedDatasetId = ref('')
const creating = ref(false)
const message = ref('')
const error = ref('')

const scenarioOptions = [
  { value: 'lead_diversion', label: '引流导流' },
  { value: 'gray_recruitment', label: '灰产招募' },
  { value: 'fraud_promotion', label: '欺诈推广' },
  { value: 'seller_risk', label: '卖家风险' },
  { value: 'product_risk', label: '商品风险' },
  { value: 'topic_watch', label: '主题监测' },
]

const selectedDataset = computed(() =>
  datasetItems.value.find((item) => item.id === selectedDatasetId.value),
)

function parseTags(text: string) {
  return text
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

async function submitDataset() {
  creating.value = true
  message.value = ''
  error.value = ''
  try {
    await createDataset({
      dataset_name: form.value.dataset_name,
      dataset_type: form.value.dataset_type,
      source_platform: form.value.source_platform,
      scenario_type: form.value.scenario_type,
      storage_uri: form.value.storage_uri,
      tags: parseTags(form.value.tags),
    })
    message.value = 'Dataset created.'
    form.value.dataset_name = ''
    form.value.storage_uri = ''
    form.value.tags = ''
    await fetchDatasets()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    creating.value = false
  }
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
  message.value = ''
  error.value = ''
  try {
    await deleteDataset(datasetId)
    message.value = 'Dataset deleted.'
    if (selectedDatasetId.value === datasetId) {
      selectedDatasetId.value = ''
      preview.value = null
    }
    await fetchDatasets()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}
</script>

<template>
  <section class="page-grid">
    <section class="surface section-card">
      <div class="section-head">
        <div>
          <h2>Create Dataset</h2>
          <p>数据集负责把抓取结果沉淀成后续可预览、可分析的标准输入。</p>
        </div>
      </div>

      <form class="dataset-form" @submit.prevent="submitDataset">
        <div class="grid-two">
          <label class="field">
            <span>Dataset Name</span>
            <input v-model="form.dataset_name" required placeholder="例：小红书情报采集 2026-04-27" />
          </label>

          <label class="field">
            <span>Source Platform</span>
            <select v-model="form.source_platform">
              <option v-for="item in platformItems" :key="item.platform" :value="item.platform">
                {{ item.label }}
              </option>
            </select>
          </label>
        </div>

        <div class="grid-two">
          <label class="field">
            <span>Dataset Type</span>
            <select v-model="form.dataset_type">
              <option value="raw">raw</option>
              <option value="normalized">normalized</option>
              <option value="analysis_ready">analysis_ready</option>
            </select>
          </label>

          <label class="field">
            <span>Risk Scenario</span>
            <select v-model="form.scenario_type">
              <option v-for="item in scenarioOptions" :key="item.value" :value="item.value">
                {{ item.label }}
              </option>
            </select>
          </label>
        </div>

        <div class="grid-two">
          <label class="field">
            <span>Tags</span>
            <input v-model="form.tags" placeholder="brand, campaign, launch" />
          </label>
          <div class="field field-empty" aria-hidden="true" />
        </div>

        <label class="field">
          <span>Storage URI</span>
          <input
            v-model="form.storage_uri"
            placeholder="例：xhs/xhs_brand_20260427.jsonl，路径相对 backend/storage/dataset_files"
          />
        </label>

        <div class="actions">
          <button class="primary-button" :disabled="creating" type="submit">
            {{ creating ? 'Creating...' : 'Create Dataset' }}
          </button>
          <span v-if="message" class="success-text">{{ message }}</span>
          <span v-if="error" class="error-text">{{ error }}</span>
        </div>
      </form>
    </section>

    <div class="split-grid">
      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Dataset Registry</h2>
            <p>优先查看 record count、来源平台和存储路径。</p>
          </div>
        </div>

        <div v-if="datasetsLoading" class="muted">Loading datasets...</div>
        <div v-else-if="datasetsError" class="error-text">{{ datasetsError }}</div>
        <div v-else class="dataset-list">
          <article v-for="item in datasetItems" :key="item.id" class="dataset-item">
            <div class="dataset-main">
              <div>
                <strong>{{ item.dataset_name }}</strong>
                <p>{{ item.source_platform }} · {{ item.scenario_type || '-' }} · {{ item.dataset_type }} · {{ item.record_count }} records</p>
              </div>
              <span class="dataset-id">{{ item.id }}</span>
            </div>
            <div class="dataset-meta">{{ item.storage_uri || 'No storage URI' }}</div>
            <div class="actions">
              <button class="secondary-button" type="button" @click="loadPreview(item.id)">Preview</button>
              <button class="secondary-button destructive" type="button" @click="removeDataset(item.id)">
                Delete
              </button>
            </div>
          </article>
          <div v-if="!datasetItems.length" class="muted">No datasets yet.</div>
        </div>
      </section>

      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Dataset Preview</h2>
            <p>{{ selectedDataset ? selectedDataset.dataset_name : '选择左侧数据集查看预览。' }}</p>
          </div>
        </div>

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
        <div v-else class="muted">No preview loaded.</div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.page-grid,
.dataset-form,
.dataset-list {
  display: grid;
  gap: 18px;
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

.primary-button,
.secondary-button {
  border: none;
  border-radius: 12px;
  padding: 10px 14px;
  font-weight: 700;
  cursor: pointer;
}

.primary-button {
  background: linear-gradient(135deg, #2563eb 0%, #0f766e 100%);
  color: white;
}

.secondary-button {
  background: rgba(226, 232, 240, 0.9);
  color: #1e293b;
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
  .split-grid,
  .grid-two {
    grid-template-columns: 1fr;
  }
}
</style>
