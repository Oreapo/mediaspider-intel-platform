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
import AppAlert from '../components/ui/AppAlert.vue'
import BaseSection from '../components/ui/BaseSection.vue'
import EmptyState from '../components/ui/EmptyState.vue'
import FieldError from '../components/ui/FieldError.vue'
import LoadingState from '../components/ui/LoadingState.vue'
import PaginationBar from '../components/ui/PaginationBar.vue'
import PermissionGate from '../components/ui/PermissionGate.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import { useEntities } from '../composables/useEntities'
import { useI18n } from '../composables/useI18n'
import { usePlatformModels } from '../composables/usePlatformModels'
import { useSignals } from '../composables/useSignals'
import { requestConfirm } from '../lib/confirm'
import { lastPageOffset } from '../lib/pagination'
import { required, type ValidationErrors } from '../lib/validation'
import type { EntityDetail } from '../types'

const {
  items: entityItems,
  total: entityTotal,
  relations,
  isLoading: entitiesLoading,
  error: entitiesError,
  fetchItems: fetchEntities,
} = useEntities()
const { items: signalItems } = useSignals()
const { items: platformItems } = usePlatformModels()
const { t } = useI18n()

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
const filters = ref({
  q: '',
  platform: '',
  entity_type: '',
  status: '',
  min_risk_score: 0,
  limit: 100,
  offset: 0,
})
const selectedDetail = ref<EntityDetail | null>(null)
const message = ref('')
const error = ref('')
const busy = ref(false)
const fromSignalErrors = ref<ValidationErrors>({})
const manualErrors = ref<ValidationErrors>({})
const relationErrors = ref<ValidationErrors>({})
const mergeErrors = ref<ValidationErrors>({})

const confirmedSignals = computed(() => signalItems.value.filter((item) => item.status === 'confirmed'))

const entityStats = computed(() => [
  { label: t('entities.active'), value: entityItems.value.filter((item) => item.status === 'active').length },
  { label: t('entities.merged'), value: entityItems.value.filter((item) => item.status === 'merged').length },
  { label: t('entities.highRiskPlus'), value: entityItems.value.filter((item) => item.risk_score >= 80).length },
  { label: t('entities.relations'), value: relations.value.length },
])

const entityTypes = computed(() => Array.from(new Set(entityItems.value.map((item) => item.entity_type))).sort())

const graphNodes = computed(() => {
  if (!selectedDetail.value) return []
  const selectedId = selectedDetail.value.entity.id
  const ids = new Set<string>([selectedId])
  selectedDetail.value.relations.forEach((relation) => {
    ids.add(relation.source_entity_id)
    ids.add(relation.target_entity_id)
  })
  const list = Array.from(ids)
  const center = { id: selectedId, label: entityName(selectedId), x: 50, y: 50, selected: true }
  const others = list.filter((id) => id !== selectedId)
  return [
    center,
    ...others.map((id, index) => {
      const angle = (Math.PI * 2 * index) / Math.max(others.length, 1) - Math.PI / 2
      return {
        id,
        label: entityName(id),
        x: 50 + Math.cos(angle) * 32,
        y: 50 + Math.sin(angle) * 32,
        selected: false,
      }
    }),
  ]
})

const graphEdges = computed(() => {
  const nodeMap = new Map(graphNodes.value.map((node) => [node.id, node]))
  return (selectedDetail.value?.relations || [])
    .map((relation) => {
      const source = nodeMap.get(relation.source_entity_id)
      const target = nodeMap.get(relation.target_entity_id)
      if (!source || !target) return null
      return {
        ...relation,
        source,
        target,
      }
    })
    .filter((edge): edge is NonNullable<typeof edge> => edge !== null)
})

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

function validateFromSignalForm() {
  const errors: ValidationErrors = {}
  const signalError = required(fromSignalForm.value.signal_id, t('entities.confirmedSignal'))
  if (signalError) errors.signal_id = signalError
  fromSignalErrors.value = errors
  return Object.keys(errors).length === 0
}

function validateManualEntityForm() {
  const errors: ValidationErrors = {}
  const nameError = required(manualForm.value.display_name, t('entities.displayName'))
  const scoreValid = Number.isFinite(manualForm.value.risk_score)
    && manualForm.value.risk_score >= 0
    && manualForm.value.risk_score <= 100

  if (nameError) errors.display_name = nameError
  if (!scoreValid) errors.risk_score = t('entities.scoreInvalid')

  manualErrors.value = errors
  return Object.keys(errors).length === 0
}

function validateRelationForm() {
  const errors: ValidationErrors = {}
  const sourceError = required(relationForm.value.source_entity_id, t('entities.source'))
  const targetError = required(relationForm.value.target_entity_id, t('entities.target'))
  const typeError = required(relationForm.value.relation_type, t('entities.relationType'))
  const confidenceValid = Number.isFinite(relationForm.value.confidence)
    && relationForm.value.confidence >= 0
    && relationForm.value.confidence <= 1

  if (sourceError) errors.source_entity_id = sourceError
  if (targetError) errors.target_entity_id = targetError
  if (typeError) errors.relation_type = typeError
  if (!confidenceValid) errors.confidence = t('entities.confidenceInvalid')
  if (
    relationForm.value.source_entity_id
    && relationForm.value.target_entity_id
    && relationForm.value.source_entity_id === relationForm.value.target_entity_id
  ) {
    errors.target_entity_id = t('entities.targetSameAsSource')
  }

  relationErrors.value = errors
  return Object.keys(errors).length === 0
}

function validateMergeForm() {
  const errors: ValidationErrors = {}
  const sourceError = required(mergeForm.value.source_entity_id, t('entities.mergeSource'))
  const targetError = required(mergeForm.value.target_entity_id, t('entities.mergeTarget'))

  if (sourceError) errors.source_entity_id = sourceError
  if (targetError) errors.target_entity_id = targetError
  if (
    mergeForm.value.source_entity_id
    && mergeForm.value.target_entity_id
    && mergeForm.value.source_entity_id === mergeForm.value.target_entity_id
  ) {
    errors.target_entity_id = t('entities.mergeSameTarget')
  }

  mergeErrors.value = errors
  return Object.keys(errors).length === 0
}

async function submitFromSignal() {
  message.value = ''
  error.value = ''
  if (!validateFromSignalForm()) {
    error.value = t('entities.fixFromSignalErrors')
    return
  }

  busy.value = true
  try {
    const entity = await createEntityFromSignal({
      signal_id: fromSignalForm.value.signal_id,
      entity_type: fromSignalForm.value.entity_type || null,
      display_name: fromSignalForm.value.display_name || null,
    })
    message.value = t('entities.createdFromSignal')
    await fetchEntityPage()
    await inspectEntity(entity.id)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function submitManualEntity() {
  message.value = ''
  error.value = ''
  if (!validateManualEntityForm()) {
    error.value = t('entities.fixManualErrors')
    return
  }

  busy.value = true
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
    message.value = t('entities.created')
    manualForm.value.display_name = ''
    manualForm.value.aliases = ''
    await fetchEntityPage()
    await inspectEntity(entity.id)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function submitRelation() {
  message.value = ''
  error.value = ''
  if (!validateRelationForm()) {
    error.value = t('entities.fixRelationErrors')
    return
  }

  busy.value = true
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
    message.value = t('entities.relationSaved')
    await fetchEntityPage()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function submitMerge() {
  message.value = ''
  error.value = ''
  if (!validateMergeForm()) {
    error.value = t('entities.fixMergeErrors')
    return
  }

  busy.value = true
  try {
    const result = await mergeEntities({
      source_entity_id: mergeForm.value.source_entity_id,
      target_entity_id: mergeForm.value.target_entity_id,
      relation_type: 'merged_alias',
      confidence: 0.95,
      evidence_ref_json: { reason: 'manual_merge' },
    })
    message.value = t('entities.mergedMessage')
    await fetchEntityPage()
    await inspectEntity(result.target_entity.id)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function applyFilters() {
  selectedDetail.value = null
  filters.value.offset = 0
  await fetchEntityPage()
}

async function fetchEntityPage() {
  await fetchEntities({
    q: filters.value.q,
    platform: filters.value.platform,
    entity_type: filters.value.entity_type,
    status: filters.value.status,
    min_risk_score: filters.value.min_risk_score || undefined,
    limit: filters.value.limit,
    offset: filters.value.offset,
  })
  const normalizedOffset = lastPageOffset(entityTotal.value, filters.value.limit)
  if (filters.value.offset > normalizedOffset) {
    filters.value.offset = normalizedOffset
    if (entityTotal.value > 0) await fetchEntityPage()
  }
}

async function changeEntityPage(offset: number) {
  selectedDetail.value = null
  filters.value.offset = offset
  await fetchEntityPage()
}

async function clearFilters() {
  filters.value = {
    q: '',
    platform: '',
    entity_type: '',
    status: '',
    min_risk_score: 0,
    limit: 100,
    offset: 0,
  }
  await applyFilters()
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
    message.value = t('entities.statusUpdated', { status: labelValue(status) })
    await fetchEntityPage()
    if (selectedDetail.value?.entity.id === entityId) await inspectEntity(entityId)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function removeEntity(entityId: string) {
  const confirmed = await requestConfirm({
    title: t('entities.deleteTitle'),
    message: t('entities.deleteMessage'),
    confirmLabel: t('entities.deleteConfirm'),
  })
  if (!confirmed) return

  message.value = ''
  error.value = ''
  try {
    await deleteEntity(entityId)
    message.value = t('entities.deletedMessage')
    if (selectedDetail.value?.entity.id === entityId) selectedDetail.value = null
    await fetchEntityPage()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

function labelValue(value: string) {
  const key = `enum.${value}`
  const translated = t(key)
  return translated === key ? value : translated
}

function scenarioLabel(value?: string | null) {
  if (!value) return '-'
  const key = `scenario.${value}`
  const translated = t(key)
  return translated === key ? value : translated
}

function entityStatusTone(status: string) {
  if (status === 'active') return 'success'
  if (status === 'merged') return 'warning'
  if (status === 'dismissed') return 'danger'
  return 'neutral'
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

    <div class="entity-workspace">
      <aside class="entity-side-panel">
        <div class="entity-action-stack">
          <BaseSection compact :title="t('entities.fromSignalTitle')" :description="t('entities.fromSignalDescription')">
            <PermissionGate area="analysis">
              <form class="entity-form" @submit.prevent="submitFromSignal">
                <label class="field">
                  <span>{{ t('entities.confirmedSignal') }}</span>
                  <select v-model="fromSignalForm.signal_id" required>
                    <option value="" disabled>{{ t('entities.chooseConfirmedSignal') }}</option>
                    <option v-for="item in confirmedSignals" :key="item.id" :value="item.id">
                      {{ item.summary }} · {{ sourceRef(item).row_index ?? '-' }}
                    </option>
                  </select>
                  <FieldError :message="fromSignalErrors.signal_id" />
                </label>

                <div class="grid-two">
                  <label class="field">
                    <span>{{ t('entities.entityType') }}</span>
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
                    <span>{{ t('entities.displayName') }}</span>
                    <input v-model="fromSignalForm.display_name" :placeholder="t('entities.displayNameAuto')" />
                  </label>
                </div>

                <div class="actions">
                  <button class="primary-button" :disabled="busy" type="submit">
                    {{ busy ? t('signals.processing') : t('entities.createEntity') }}
                  </button>
                </div>
              </form>
            </PermissionGate>
          </BaseSection>

          <BaseSection compact :title="t('entities.manualTitle')" :description="t('entities.manualDescription')">
            <PermissionGate area="analysis">
              <form class="entity-form" @submit.prevent="submitManualEntity">
                <div class="grid-two">
                  <label class="field">
                    <span>{{ t('entities.entityType') }}</span>
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
                    <span>{{ t('entities.platform') }}</span>
                    <select v-model="manualForm.platform">
                      <option v-for="item in platformItems" :key="item.platform" :value="item.platform">
                        {{ item.label }}
                      </option>
                    </select>
                  </label>
                </div>

                <div class="grid-two">
                  <label class="field">
                    <span>{{ t('entities.displayName') }}</span>
                    <input v-model="manualForm.display_name" required placeholder="例：risk_account_01" />
                    <FieldError :message="manualErrors.display_name" />
                  </label>
                  <label class="field">
                    <span>{{ t('entities.riskScore') }}</span>
                    <input v-model.number="manualForm.risk_score" min="0" max="100" step="1" type="number" />
                    <FieldError :message="manualErrors.risk_score" />
                  </label>
                </div>

                <label class="field">
                  <span>{{ t('entities.aliases') }}</span>
                  <input v-model="manualForm.aliases" :placeholder="t('entities.aliasesPlaceholder')" />
                </label>

                <div class="actions">
                  <button class="secondary-button" :disabled="busy" type="submit">{{ t('entities.createManual') }}</button>
                </div>
              </form>
            </PermissionGate>
          </BaseSection>

          <BaseSection compact :title="t('entities.relationTitle')" :description="t('entities.relationDescription')">
            <PermissionGate area="analysis">
              <form class="entity-form" @submit.prevent="submitRelation">
                <div class="grid-two">
                  <label class="field">
                    <span>{{ t('entities.source') }}</span>
                    <select v-model="relationForm.source_entity_id" required>
                      <option value="" disabled>{{ t('entities.chooseSource') }}</option>
                      <option v-for="item in entityItems" :key="item.id" :value="item.id">
                        {{ item.display_name }} · {{ item.entity_type }}
                      </option>
                    </select>
                    <FieldError :message="relationErrors.source_entity_id" />
                  </label>
                  <label class="field">
                    <span>{{ t('entities.target') }}</span>
                    <select v-model="relationForm.target_entity_id" required>
                      <option value="" disabled>{{ t('entities.chooseTarget') }}</option>
                      <option v-for="item in entityItems" :key="item.id" :value="item.id">
                        {{ item.display_name }} · {{ item.entity_type }}
                      </option>
                    </select>
                    <FieldError :message="relationErrors.target_entity_id" />
                  </label>
                </div>

                <div class="grid-two">
                  <label class="field">
                    <span>{{ t('entities.relationType') }}</span>
                    <input v-model="relationForm.relation_type" required placeholder="uses_contact_point" />
                    <FieldError :message="relationErrors.relation_type" />
                  </label>
                  <label class="field">
                    <span>{{ t('entities.confidence') }}</span>
                    <input v-model.number="relationForm.confidence" min="0" max="1" step="0.01" type="number" />
                    <FieldError :message="relationErrors.confidence" />
                  </label>
                </div>

                <label class="field">
                  <span>{{ t('entities.evidenceRef') }}</span>
                  <input v-model="relationForm.evidence_ref" :placeholder="t('entities.evidencePlaceholder')" />
                </label>

                <div class="actions">
                  <button class="secondary-button" :disabled="busy" type="submit">{{ t('entities.saveRelation') }}</button>
                </div>
              </form>
            </PermissionGate>
          </BaseSection>

          <BaseSection compact :title="t('entities.mergeTitle')" :description="t('entities.mergeDescription')">
            <PermissionGate area="analysis">
              <form class="entity-form" @submit.prevent="submitMerge">
                <div class="grid-two">
                  <label class="field">
                    <span>{{ t('entities.mergeSource') }}</span>
                    <select v-model="mergeForm.source_entity_id" required>
                      <option value="" disabled>{{ t('entities.chooseMergedSource') }}</option>
                      <option v-for="item in entityItems" :key="item.id" :value="item.id">
                        {{ item.display_name }}
                      </option>
                    </select>
                    <FieldError :message="mergeErrors.source_entity_id" />
                  </label>
                  <label class="field">
                    <span>{{ t('entities.mergeTo') }}</span>
                    <select v-model="mergeForm.target_entity_id" required>
                      <option value="" disabled>{{ t('entities.chooseTarget') }}</option>
                      <option v-for="item in entityItems" :key="item.id" :value="item.id">
                        {{ item.display_name }}
                      </option>
                    </select>
                    <FieldError :message="mergeErrors.target_entity_id" />
                  </label>
                </div>

                <div class="actions">
                  <button class="secondary-button" :disabled="busy" type="submit">{{ t('entities.merge') }}</button>
                </div>
              </form>
            </PermissionGate>
          </BaseSection>
        </div>

        <AppAlert v-if="message" tone="success" :title="t('tasks.successTitle')" :message="message" />
        <AppAlert v-if="error" tone="error" :title="t('tasks.actionFailedTitle')" :message="error" />
      </aside>

      <main class="entity-main-panel">
        <div class="split-grid">
      <BaseSection :title="t('entities.listTitle')" :description="t('entities.listDescription')">
        <form class="filter-form" @submit.prevent="applyFilters">
          <label class="field">
            <span>{{ t('tasks.search') }}</span>
            <input v-model="filters.q" :placeholder="t('entities.searchPlaceholder')" />
          </label>

          <label class="field">
            <span>{{ t('entities.platform') }}</span>
            <select v-model="filters.platform">
              <option value="">{{ t('entities.allPlatforms') }}</option>
              <option v-for="item in platformItems" :key="item.platform" :value="item.platform">
                {{ item.label }}
              </option>
            </select>
          </label>

          <label class="field">
            <span>{{ t('signals.type') }}</span>
            <select v-model="filters.entity_type">
              <option value="">{{ t('entities.allTypes') }}</option>
              <option v-for="item in entityTypes" :key="item" :value="item">{{ item }}</option>
            </select>
          </label>

          <label class="field">
            <span>{{ t('tasks.status') }}</span>
            <select v-model="filters.status">
              <option value="">{{ t('signals.allStatuses') }}</option>
              <option value="active">{{ t('enum.active') }}</option>
              <option value="merged">{{ t('enum.merged') }}</option>
              <option value="dismissed">{{ t('enum.dismissed') }}</option>
            </select>
          </label>

          <label class="field">
            <span>{{ t('entities.minRisk') }}</span>
            <input v-model.number="filters.min_risk_score" min="0" max="100" step="1" type="number" />
          </label>

          <label class="field">
            <span>{{ t('tasks.limit') }}</span>
            <input v-model.number="filters.limit" min="1" max="500" step="1" type="number" />
          </label>

          <div class="actions filter-actions">
            <button class="primary-button" :disabled="entitiesLoading" type="submit">{{ t('tasks.apply') }}</button>
            <button class="secondary-button" :disabled="entitiesLoading" type="button" @click="clearFilters">{{ t('tasks.clear') }}</button>
          </div>
        </form>

        <LoadingState v-if="entitiesLoading" :title="t('entities.loading')" />
        <AppAlert v-else-if="entitiesError" tone="error" :title="t('common.loadFailed')" :message="entitiesError" />
        <div v-else class="entity-list">
          <article v-for="item in entityItems" :key="item.id" class="entity-item">
            <div class="entity-main">
              <div>
                <strong>{{ item.display_name }}</strong>
                <p>{{ item.platform }} · {{ item.entity_type }} · score {{ item.risk_score }}</p>
              </div>
              <div class="badge-stack">
              <StatusBadge :label="labelValue(item.status)" :tone="entityStatusTone(item.status)" />
              </div>
            </div>
            <div class="entity-meta">
              <span>{{ item.id }}</span>
              <span>{{ t('entities.linkedSignalCount', { count: (item.profile_json.linked_signal_ids as unknown[])?.length || 0 }) }}</span>
            </div>
            <div class="actions">
              <button class="secondary-button" type="button" @click="inspectEntity(item.id)">{{ t('entities.view') }}</button>
              <PermissionGate area="analysis" compact>
              <button class="secondary-button" type="button" @click="setStatus(item.id, 'active')">{{ t('entities.activate') }}</button>
              <button class="secondary-button" type="button" @click="setStatus(item.id, 'dismissed')">{{ t('entities.dismiss') }}</button>
              <button class="secondary-button destructive" type="button" @click="removeEntity(item.id)">{{ t('entities.delete') }}</button>
              </PermissionGate>
            </div>
          </article>
          <EmptyState v-if="!entityItems.length" :title="t('entities.emptyTitle')" :description="t('entities.emptyDescription')" />
          <PaginationBar
            :total="entityTotal"
            :limit="filters.limit"
            :offset="filters.offset"
            :loading="entitiesLoading"
            @change="changeEntityPage"
          />
        </div>
      </BaseSection>

      <BaseSection :title="t('entities.detailTitle')" :description="selectedDetail ? selectedDetail.entity.id : t('entities.detailDescription')">
        <div v-if="selectedDetail" class="detail-wrap">
          <div class="detail-card">
            <strong>{{ selectedDetail.entity.display_name }}</strong>
            <p>{{ selectedDetail.entity.platform }} · {{ selectedDetail.entity.entity_type }}</p>
            <pre>{{ JSON.stringify(selectedDetail.entity.source_ref, null, 2) }}</pre>
          </div>

          <div class="detail-section">
            <h3>{{ t('entities.graphTitle') }}</h3>
            <div v-if="graphNodes.length" class="relation-graph">
              <svg viewBox="0 0 100 100" role="img" :aria-label="t('entities.graphAria')">
                <g>
                  <line
                    v-for="edge in graphEdges"
                    :key="edge.id"
                    :x1="edge.source.x"
                    :y1="edge.source.y"
                    :x2="edge.target.x"
                    :y2="edge.target.y"
                    class="graph-edge"
                    :class="{ strong: edge.confidence >= 0.8 }"
                  />
                </g>
                <g>
                  <circle
                    v-for="node in graphNodes"
                    :key="node.id"
                    :cx="node.x"
                    :cy="node.y"
                    :r="node.selected ? 8 : 6"
                    class="graph-node"
                    :class="{ selected: node.selected }"
                  />
                  <text
                    v-for="node in graphNodes"
                    :key="`${node.id}-label`"
                    :x="node.x"
                    :y="node.y + (node.selected ? 13 : 11)"
                    text-anchor="middle"
                    class="graph-label"
                  >
                    {{ node.label.slice(0, 12) }}
                  </text>
                </g>
              </svg>
              <div class="graph-legend">
                <span>{{ t('entities.centerNode') }}</span>
                <span>{{ t('entities.strongLine') }}</span>
              </div>
            </div>
            <EmptyState v-else :title="t('entities.noGraphTitle')" :description="t('entities.noGraphDescription')" />
          </div>

          <div class="detail-section">
            <h3>{{ t('entities.signals') }}</h3>
            <article v-for="item in selectedDetail.signals" :key="item.id" class="compact-item">
              <strong>{{ item.summary }}</strong>
              <span>{{ item.signal_type }} · {{ labelValue(item.status) }}</span>
            </article>
            <EmptyState v-if="!selectedDetail.signals.length" :title="t('entities.noSignals')" />
          </div>

          <div class="detail-section">
            <h3>{{ t('entities.relations') }}</h3>
            <article v-for="item in selectedDetail.relations" :key="item.id" class="compact-item">
              <strong>{{ entityName(item.source_entity_id) }} -> {{ entityName(item.target_entity_id) }}</strong>
              <span>{{ item.relation_type }} · {{ item.confidence }}</span>
            </article>
            <EmptyState v-if="!selectedDetail.relations.length" :title="t('entities.noRelations')" />
          </div>

          <div class="detail-section">
            <h3>{{ t('entities.datasets') }}</h3>
            <article v-for="item in selectedDetail.datasets" :key="item.id" class="compact-item">
              <strong>{{ item.dataset_name }}</strong>
              <span>{{ item.source_platform }} · {{ scenarioLabel(item.scenario_type) }}</span>
            </article>
            <EmptyState v-if="!selectedDetail.datasets.length" :title="t('entities.noDatasets')" />
          </div>
        </div>
        <EmptyState v-else :title="t('entities.noSelectionTitle')" :description="t('entities.noSelectionDescription')" />
      </BaseSection>
        </div>
      </main>
    </div>
  </section>
</template>

<style scoped>
.page-grid,
.entity-form,
.entity-list,
.detail-wrap,
.filter-form {
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

.entity-workspace {
  display: grid;
  grid-template-columns: minmax(320px, 390px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.entity-side-panel {
  position: sticky;
  top: 86px;
  max-height: calc(100vh - 104px);
  min-width: 0;
  display: grid;
  gap: 14px;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding-right: 2px;
}

.entity-main-panel {
  min-width: 0;
}

.entity-action-stack {
  display: grid;
  gap: 14px;
}

.entity-side-panel .grid-two {
  grid-template-columns: 1fr;
}

.entity-side-panel .actions {
  display: grid;
}

.entity-side-panel .primary-button,
.entity-side-panel .secondary-button {
  width: 100%;
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

.filter-form {
  grid-template-columns: 1.3fr repeat(5, minmax(0, 1fr)) auto;
  align-items: end;
  margin-bottom: 18px;
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

.relation-graph {
  display: grid;
  gap: 10px;
  padding: 12px;
  border-radius: 16px;
  border: 1px solid rgba(203, 213, 225, 0.9);
  background: rgba(255, 255, 255, 0.76);
}

.relation-graph svg {
  width: 100%;
  aspect-ratio: 1.7;
  min-height: 240px;
}

.graph-edge {
  stroke: rgba(100, 116, 139, 0.55);
  stroke-width: 0.7;
}

.graph-edge.strong {
  stroke: #2563eb;
  stroke-width: 1.3;
}

.graph-node {
  fill: #94a3b8;
  stroke: white;
  stroke-width: 1.4;
}

.graph-node.selected {
  fill: #2563eb;
}

.graph-label {
  fill: #334155;
  font-size: 4px;
  font-weight: 700;
}

.graph-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  color: #64748b;
  font-size: 13px;
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

  .entity-workspace {
    grid-template-columns: 1fr;
  }

  .entity-side-panel {
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
