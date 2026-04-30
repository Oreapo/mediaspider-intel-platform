<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  createEntity,
  createEntityFromSignal,
  createRelation,
  deleteEntity,
  getEntityDetail,
  mergeEntities,
  updateEntityStatus,
} from '../api/entities'
import { useEntities } from '../composables/useEntities'
import { usePlatformModels } from '../composables/usePlatformModels'
import { useSignals } from '../composables/useSignals'
import type { EntityDetail } from '../types'

const {
  items: entityItems,
  relations,
  isLoading: entitiesLoading,
  error: entitiesError,
  fetchItems: fetchEntities,
} = useEntities()
const { items: signalItems } = useSignals()
const { items: platformItems } = usePlatformModels()

const fromSignalForm = ref({
  signal_id: '',
  entity_type: '',
  display_name: '',
})
const manualForm = ref({
  entity_type: 'account',
  display_name: '',
  platform: 'xhs',
  risk_score: 50,
  aliases: '',
})
const relationForm = ref({
  source_entity_id: '',
  target_entity_id: '',
  relation_type: 'linked_by_signal',
  confidence: 0.8,
  evidence_ref: '',
})
const mergeForm = ref({
  source_entity_id: '',
  target_entity_id: '',
})
const selectedDetail = ref<EntityDetail | null>(null)
const message = ref('')
const error = ref('')
const busy = ref(false)

const confirmedSignals = computed(() => signalItems.value.filter((item) => item.status === 'confirmed'))

const entityStats = computed(() => [
  { label: 'Active', value: entityItems.value.filter((item) => item.status === 'active').length },
  { label: 'Merged', value: entityItems.value.filter((item) => item.status === 'merged').length },
  { label: 'High+', value: entityItems.value.filter((item) => item.risk_score >= 80).length },
  { label: 'Relations', value: relations.value.length },
])

function sourceRef(signal: { payload_json: Record<string, unknown> }) {
  const ref = signal.payload_json.source_ref
  return ref && typeof ref === 'object' ? (ref as Record<string, unknown>) : {}
}

function parseAliases(text: string) {
  return text
    .split(',')
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean)
}

function entityName(entityId: string) {
  return entityItems.value.find((item) => item.id === entityId)?.display_name || entityId
}

async function submitFromSignal() {
  busy.value = true
  message.value = ''
  error.value = ''
  try {
    const entity = await createEntityFromSignal({
      signal_id: fromSignalForm.value.signal_id,
      entity_type: fromSignalForm.value.entity_type || null,
      display_name: fromSignalForm.value.display_name || null,
    })
    message.value = 'Entity created from signal.'
    await fetchEntities()
    await inspectEntity(entity.id)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function submitManualEntity() {
  busy.value = true
  message.value = ''
  error.value = ''
  try {
    const aliases = parseAliases(manualForm.value.aliases)
    const entity = await createEntity({
      entity_type: manualForm.value.entity_type,
      display_name: manualForm.value.display_name,
      platform: manualForm.value.platform,
      risk_score: manualForm.value.risk_score,
      source_ref: { display_name: manualForm.value.display_name },
      profile_json: { aliases },
    })
    message.value = 'Entity created.'
    manualForm.value.display_name = ''
    manualForm.value.aliases = ''
    await fetchEntities()
    await inspectEntity(entity.id)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function submitRelation() {
  busy.value = true
  message.value = ''
  error.value = ''
  try {
    await createRelation({
      source_entity_id: relationForm.value.source_entity_id,
      target_entity_id: relationForm.value.target_entity_id,
      relation_type: relationForm.value.relation_type,
      confidence: relationForm.value.confidence,
      evidence_ref_json: relationForm.value.evidence_ref
        ? { note: relationForm.value.evidence_ref }
        : {},
    })
    message.value = 'Relation saved.'
    await fetchEntities()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function submitMerge() {
  busy.value = true
  message.value = ''
  error.value = ''
  try {
    const result = await mergeEntities({
      source_entity_id: mergeForm.value.source_entity_id,
      target_entity_id: mergeForm.value.target_entity_id,
      relation_type: 'merged_alias',
      confidence: 0.95,
      evidence_ref_json: { reason: 'manual_merge' },
    })
    message.value = 'Entities merged.'
    await fetchEntities()
    await inspectEntity(result.target_entity.id)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function inspectEntity(entityId: string) {
  message.value = ''
  error.value = ''
  try {
    selectedDetail.value = await getEntityDetail(entityId)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function setStatus(entityId: string, status: string) {
  message.value = ''
  error.value = ''
  try {
    await updateEntityStatus(entityId, status)
    message.value = `Entity marked as ${status}.`
    await fetchEntities()
    if (selectedDetail.value?.entity.id === entityId) await inspectEntity(entityId)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function removeEntity(entityId: string) {
  message.value = ''
  error.value = ''
  try {
    await deleteEntity(entityId)
    message.value = 'Entity deleted.'
    if (selectedDetail.value?.entity.id === entityId) selectedDetail.value = null
    await fetchEntities()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}
</script>

<template>
  <section class="page-grid">
    <div class="stats-grid">
      <article v-for="stat in entityStats" :key="stat.label" class="surface stat-card">
        <span>{{ stat.label }}</span>
        <strong>{{ stat.value }}</strong>
      </article>
    </div>

    <div class="split-grid">
      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Create From Signal</h2>
            <p>只允许从 confirmed 信号生成实体，确保研判对象有复核来源。</p>
          </div>
        </div>

        <form class="entity-form" @submit.prevent="submitFromSignal">
          <label class="field">
            <span>Confirmed Signal</span>
            <select v-model="fromSignalForm.signal_id" required>
              <option value="" disabled>选择 confirmed 信号</option>
              <option v-for="item in confirmedSignals" :key="item.id" :value="item.id">
                {{ item.summary }} · {{ sourceRef(item).row_index ?? '-' }}
              </option>
            </select>
          </label>

          <div class="grid-two">
            <label class="field">
              <span>Entity Type</span>
              <select v-model="fromSignalForm.entity_type">
                <option value="">auto</option>
                <option value="account">account</option>
                <option value="seller">seller</option>
                <option value="product">product</option>
                <option value="content">content</option>
                <option value="contact_point">contact_point</option>
                <option value="alias">alias</option>
              </select>
            </label>
            <label class="field">
              <span>Display Name</span>
              <input v-model="fromSignalForm.display_name" placeholder="留空则自动从 signal 推断" />
            </label>
          </div>

          <div class="actions">
            <button class="primary-button" :disabled="busy" type="submit">
              {{ busy ? 'Working...' : 'Create Entity' }}
            </button>
          </div>
        </form>
      </section>

      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Manual Entity</h2>
            <p>用于分析师手工登记账号、卖家、商品或联系方式等风险对象。</p>
          </div>
        </div>

        <form class="entity-form" @submit.prevent="submitManualEntity">
          <div class="grid-two">
            <label class="field">
              <span>Entity Type</span>
              <select v-model="manualForm.entity_type">
                <option value="account">account</option>
                <option value="seller">seller</option>
                <option value="product">product</option>
                <option value="content">content</option>
                <option value="contact_point">contact_point</option>
                <option value="alias">alias</option>
                <option value="unknown">unknown</option>
              </select>
            </label>
            <label class="field">
              <span>Platform</span>
              <select v-model="manualForm.platform">
                <option v-for="item in platformItems" :key="item.platform" :value="item.platform">
                  {{ item.label }}
                </option>
              </select>
            </label>
          </div>

          <div class="grid-two">
            <label class="field">
              <span>Display Name</span>
              <input v-model="manualForm.display_name" required placeholder="例：risk_account_01" />
            </label>
            <label class="field">
              <span>Risk Score</span>
              <input v-model.number="manualForm.risk_score" min="0" max="100" step="1" type="number" />
            </label>
          </div>

          <label class="field">
            <span>Aliases</span>
            <input v-model="manualForm.aliases" placeholder="多个别名用英文逗号分隔" />
          </label>

          <div class="actions">
            <button class="secondary-button" :disabled="busy" type="submit">Create Manual Entity</button>
          </div>
        </form>
      </section>
    </div>

    <div class="split-grid">
      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Create Relation</h2>
            <p>关系边必须有置信度和证据引用，重复边会合并。</p>
          </div>
        </div>

        <form class="entity-form" @submit.prevent="submitRelation">
          <div class="grid-two">
            <label class="field">
              <span>Source</span>
              <select v-model="relationForm.source_entity_id" required>
                <option value="" disabled>选择源实体</option>
                <option v-for="item in entityItems" :key="item.id" :value="item.id">
                  {{ item.display_name }} · {{ item.entity_type }}
                </option>
              </select>
            </label>
            <label class="field">
              <span>Target</span>
              <select v-model="relationForm.target_entity_id" required>
                <option value="" disabled>选择目标实体</option>
                <option v-for="item in entityItems" :key="item.id" :value="item.id">
                  {{ item.display_name }} · {{ item.entity_type }}
                </option>
              </select>
            </label>
          </div>

          <div class="grid-two">
            <label class="field">
              <span>Relation Type</span>
              <input v-model="relationForm.relation_type" required placeholder="uses_contact_point" />
            </label>
            <label class="field">
              <span>Confidence</span>
              <input v-model.number="relationForm.confidence" min="0" max="1" step="0.01" type="number" />
            </label>
          </div>

          <label class="field">
            <span>Evidence Note</span>
            <input v-model="relationForm.evidence_ref" placeholder="证据说明或信号 ID" />
          </label>

          <div class="actions">
            <button class="secondary-button" :disabled="busy" type="submit">Save Relation</button>
          </div>
        </form>
      </section>

      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Merge Entities</h2>
            <p>用于确认两个对象是同一风险实体时做显式合并。</p>
          </div>
        </div>

        <form class="entity-form" @submit.prevent="submitMerge">
          <div class="grid-two">
            <label class="field">
              <span>Merge Source</span>
              <select v-model="mergeForm.source_entity_id" required>
                <option value="" disabled>选择被合并实体</option>
                <option v-for="item in entityItems" :key="item.id" :value="item.id">
                  {{ item.display_name }}
                </option>
              </select>
            </label>
            <label class="field">
              <span>Merge Into</span>
              <select v-model="mergeForm.target_entity_id" required>
                <option value="" disabled>选择目标实体</option>
                <option v-for="item in entityItems" :key="item.id" :value="item.id">
                  {{ item.display_name }}
                </option>
              </select>
            </label>
          </div>

          <div class="actions">
            <button class="secondary-button" :disabled="busy" type="submit">Merge</button>
          </div>
        </form>
      </section>
    </div>

    <div v-if="message" class="success-text">{{ message }}</div>
    <div v-if="error" class="error-text">{{ error }}</div>

    <div class="split-grid">
      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Entity Registry</h2>
            <p>风险对象列表，后续案件会从这里挂接实体。</p>
          </div>
        </div>

        <div v-if="entitiesLoading" class="muted">Loading entities...</div>
        <div v-else-if="entitiesError" class="error-text">{{ entitiesError }}</div>
        <div v-else class="entity-list">
          <article v-for="item in entityItems" :key="item.id" class="entity-item">
            <div class="entity-main">
              <div>
                <strong>{{ item.display_name }}</strong>
                <p>{{ item.platform }} · {{ item.entity_type }} · score {{ item.risk_score }}</p>
              </div>
              <div class="badge-stack">
                <span class="status-badge" :class="item.status">{{ item.status }}</span>
              </div>
            </div>
            <div class="entity-meta">
              <span>{{ item.id }}</span>
              <span>{{ (item.profile_json.linked_signal_ids as unknown[])?.length || 0 }} signals</span>
            </div>
            <div class="actions">
              <button class="secondary-button" type="button" @click="inspectEntity(item.id)">Inspect</button>
              <button class="secondary-button" type="button" @click="setStatus(item.id, 'active')">Active</button>
              <button class="secondary-button" type="button" @click="setStatus(item.id, 'dismissed')">Dismiss</button>
              <button class="secondary-button destructive" type="button" @click="removeEntity(item.id)">Delete</button>
            </div>
          </article>
          <div v-if="!entityItems.length" class="muted">No entities yet.</div>
        </div>
      </section>

      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Entity Detail</h2>
            <p>{{ selectedDetail ? selectedDetail.entity.id : '选择一个实体查看信号、数据集和关系。' }}</p>
          </div>
        </div>

        <div v-if="selectedDetail" class="detail-wrap">
          <div class="detail-card">
            <strong>{{ selectedDetail.entity.display_name }}</strong>
            <p>{{ selectedDetail.entity.platform }} · {{ selectedDetail.entity.entity_type }}</p>
            <pre>{{ JSON.stringify(selectedDetail.entity.source_ref, null, 2) }}</pre>
          </div>

          <div class="detail-section">
            <h3>Signals</h3>
            <article v-for="item in selectedDetail.signals" :key="item.id" class="compact-item">
              <strong>{{ item.summary }}</strong>
              <span>{{ item.signal_type }} · {{ item.status }}</span>
            </article>
            <div v-if="!selectedDetail.signals.length" class="muted">No linked signals.</div>
          </div>

          <div class="detail-section">
            <h3>Relations</h3>
            <article v-for="item in selectedDetail.relations" :key="item.id" class="compact-item">
              <strong>{{ entityName(item.source_entity_id) }} -> {{ entityName(item.target_entity_id) }}</strong>
              <span>{{ item.relation_type }} · {{ item.confidence }}</span>
            </article>
            <div v-if="!selectedDetail.relations.length" class="muted">No relations.</div>
          </div>

          <div class="detail-section">
            <h3>Datasets</h3>
            <article v-for="item in selectedDetail.datasets" :key="item.id" class="compact-item">
              <strong>{{ item.dataset_name }}</strong>
              <span>{{ item.source_platform }} · {{ item.scenario_type || '-' }}</span>
            </article>
            <div v-if="!selectedDetail.datasets.length" class="muted">No linked datasets.</div>
          </div>
        </div>
        <div v-else class="muted">No entity selected.</div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.page-grid,
.entity-form,
.entity-list,
.detail-wrap {
  display: grid;
  gap: 18px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.split-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
}

.section-card,
.stat-card {
  border-radius: 24px;
  padding: 22px;
}

.stat-card span,
.section-head p,
.muted,
.field span,
.entity-item p,
.entity-meta,
.detail-card p,
.compact-item span {
  color: #64748b;
}

.stat-card strong {
  display: block;
  margin-top: 6px;
  font-size: 34px;
}

.section-head {
  margin-bottom: 16px;
}

.section-head h2,
.detail-section h3 {
  margin: 0 0 6px;
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

.entity-item,
.detail-card,
.compact-item {
  padding: 16px;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(248, 250, 252, 0.82);
}

.entity-main {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.entity-main strong,
.detail-card strong,
.compact-item strong {
  display: block;
  margin-bottom: 4px;
}

.entity-main p,
.detail-card p {
  margin: 0;
}

.badge-stack {
  display: grid;
  justify-items: end;
}

.status-badge {
  border-radius: 999px;
  padding: 6px 10px;
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.status-badge.merged {
  background: rgba(217, 119, 6, 0.12);
  color: #b45309;
}

.status-badge.dismissed {
  background: rgba(239, 68, 68, 0.12);
  color: #b91c1c;
}

.entity-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin: 12px 0;
  font-size: 13px;
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

.detail-section {
  display: grid;
  gap: 10px;
}

pre {
  margin: 14px 0 0;
  padding: 14px;
  overflow: auto;
  border-radius: 14px;
  background: #0f172a;
  color: #e2e8f0;
}

.success-text {
  color: #15803d;
}

.error-text {
  color: #dc2626;
}

@media (max-width: 980px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .split-grid,
  .grid-two {
    grid-template-columns: 1fr;
  }
}
</style>
