<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  deleteEvidencePacket,
  downloadEvidencePacket,
  generateEvidencePacket,
  getEvidencePacket,
} from '../api/evidence'
import AppAlert from '../components/ui/AppAlert.vue'
import BaseSection from '../components/ui/BaseSection.vue'
import EmptyState from '../components/ui/EmptyState.vue'
import FieldError from '../components/ui/FieldError.vue'
import LoadingState from '../components/ui/LoadingState.vue'
import PaginationBar from '../components/ui/PaginationBar.vue'
import PermissionGate from '../components/ui/PermissionGate.vue'
import StatusBadge from '../components/ui/StatusBadge.vue'
import { useCases } from '../composables/useCases'
import { useEvidencePackets } from '../composables/useEvidencePackets'
import { useI18n } from '../composables/useI18n'
import { requestConfirm } from '../lib/confirm'
import { lastPageOffset } from '../lib/pagination'
import { required, type ValidationErrors } from '../lib/validation'
import type { EvidencePacket } from '../types'

const packetLimit = 12
const packetOffset = ref(0)
const {
  items: packetItems,
  total: packetTotal,
  isLoading: packetsLoading,
  error: packetsError,
  fetchItems: fetchPackets,
} = useEvidencePackets({ limit: packetLimit, offset: 0 })
const { items: caseItems } = useCases()
const { t } = useI18n()

const form = ref({
  case_id: '',
  packet_name: '',
})
const selectedPacket = ref<EvidencePacket | null>(null)
const busy = ref(false)
const downloadingPacketId = ref('')
const message = ref('')
const error = ref('')
const formErrors = ref<ValidationErrors>({})

const packetStats = computed(() => [
  { label: t('evidence.statsPackets'), value: packetTotal.value },
  { label: t('evidence.statsCases'), value: new Set(packetItems.value.map((item) => item.case_id)).size },
  { label: t('evidence.statsWithArtifact'), value: packetItems.value.filter((item) => item.storage_uri).length },
  { label: t('evidence.statsLatest'), value: packetItems.value[0]?.packet_name || '-' },
])

function manifestSummary(packet: EvidencePacket | null) {
  const summary = packet?.manifest_json.summary
  return summary && typeof summary === 'object' ? (summary as Record<string, unknown>) : {}
}

function sourceRecords(packet: EvidencePacket | null) {
  const records = packet?.manifest_json.source_records
  return Array.isArray(records) ? (records as Array<Record<string, unknown>>) : []
}

async function fetchPacketPage(offset = packetOffset.value) {
  packetOffset.value = offset
  await fetchPackets({ limit: packetLimit, offset })
  const normalizedOffset = lastPageOffset(packetTotal.value, packetLimit)
  if (packetOffset.value > normalizedOffset) {
    packetOffset.value = normalizedOffset
    if (packetTotal.value > 0) {
      await fetchPackets({ limit: packetLimit, offset: normalizedOffset })
    }
  }
}

async function changePacketPage(offset: number) {
  selectedPacket.value = null
  await fetchPacketPage(offset)
}

function validatePacketForm() {
  const errors: ValidationErrors = {}
  const caseError = required(form.value.case_id, t('cases.case'))
  const nameError = required(form.value.packet_name, t('cases.evidencePacketName'))

  if (caseError) errors.case_id = caseError
  if (nameError) errors.packet_name = nameError

  formErrors.value = errors
  return Object.keys(errors).length === 0
}

async function submitPacket() {
  message.value = ''
  error.value = ''
  if (!validatePacketForm()) {
    error.value = t('evidence.fixFormErrors')
    return
  }

  busy.value = true
  try {
    const packet = await generateEvidencePacket({
      case_id: form.value.case_id,
      packet_name: form.value.packet_name,
    })
    message.value = t('evidence.generatedMessage')
    form.value.packet_name = ''
    await fetchPacketPage(0)
    selectedPacket.value = packet
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function inspectPacket(packetId: string) {
  message.value = ''
  error.value = ''
  try {
    selectedPacket.value = await getEvidencePacket(packetId)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function downloadPacket(packetId: string) {
  message.value = ''
  error.value = ''
  downloadingPacketId.value = packetId
  try {
    await downloadEvidencePacket(packetId)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    downloadingPacketId.value = ''
  }
}

async function removePacket(packetId: string) {
  const confirmed = await requestConfirm({
    title: t('evidence.deleteTitle'),
    message: t('evidence.deleteMessage'),
    confirmLabel: t('evidence.deleteConfirm'),
  })
  if (!confirmed) return

  message.value = ''
  error.value = ''
  try {
    await deleteEvidencePacket(packetId, true)
    message.value = t('evidence.deletedMessage')
    if (selectedPacket.value?.id === packetId) selectedPacket.value = null
    await fetchPacketPage()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}
</script>

<template>
  <section class="page-grid">
    <div class="stats-grid">
      <article v-for="stat in packetStats" :key="stat.label" class="surface stat-card">
        <span>{{ stat.label }}</span>
        <strong>{{ stat.value }}</strong>
      </article>
    </div>

    <div class="evidence-workspace">
      <aside class="evidence-side-panel">
        <BaseSection compact :title="t('evidence.generateTitle')" :description="t('evidence.generateDescription')">
          <PermissionGate area="analysis">
            <form class="evidence-form" @submit.prevent="submitPacket">
              <label class="field">
                <span>{{ t('cases.case') }}</span>
                <select v-model="form.case_id" required>
                  <option value="" disabled>{{ t('cases.chooseCase') }}</option>
                  <option v-for="item in caseItems" :key="item.id" :value="item.id">
                    {{ item.case_name }} · {{ t(`enum.${item.status}`) }} · {{ t(`enum.${item.priority}`) }}
                  </option>
                </select>
                <FieldError :message="formErrors.case_id" />
              </label>

              <label class="field">
                <span>{{ t('cases.evidencePacketName') }}</span>
                <input v-model="form.packet_name" required :placeholder="t('evidence.packetNamePlaceholder')" />
                <FieldError :message="formErrors.packet_name" />
              </label>

              <div class="actions">
                <button class="primary-button" :disabled="busy" type="submit">
                  {{ busy ? t('cases.generating') : t('cases.generateEvidence') }}
                </button>
              </div>
            </form>
          </PermissionGate>
        </BaseSection>

        <AppAlert v-if="message" tone="success" :title="t('tasks.successTitle')" :message="message" />
        <AppAlert v-if="error" tone="error" :title="t('tasks.actionFailedTitle')" :message="error" />
      </aside>

      <main class="evidence-main-panel">
        <BaseSection :title="t('evidence.listTitle')" :description="t('evidence.listDescription')">
          <LoadingState v-if="packetsLoading" :title="t('evidence.loading')" />
          <AppAlert v-else-if="packetsError" tone="error" :title="t('common.loadFailed')" :message="packetsError" />
          <div v-else class="packet-list">
            <article v-for="item in packetItems" :key="item.id" class="packet-item">
              <div class="packet-main">
                <div>
                  <strong>{{ item.packet_name }}</strong>
                  <p>{{ item.case_id }} · {{ item.storage_uri }}</p>
                </div>
                <StatusBadge :label="item.storage_uri ? t('evidence.downloadable') : t('evidence.notWritten')" :tone="item.storage_uri ? 'success' : 'warning'" />
              </div>
              <code class="packet-id">{{ item.id }}</code>
              <div class="actions">
                <button class="secondary-button" type="button" @click="inspectPacket(item.id)">{{ t('cases.view') }}</button>
                <button
                  class="secondary-button"
                  type="button"
                  :disabled="downloadingPacketId === item.id"
                  @click="downloadPacket(item.id)"
                >
                  {{ t('cases.download') }}
                </button>
                <PermissionGate area="analysis" compact>
                  <button class="secondary-button destructive" type="button" @click="removePacket(item.id)">{{ t('cases.delete') }}</button>
                </PermissionGate>
              </div>
            </article>
            <EmptyState v-if="!packetItems.length" :title="t('evidence.emptyTitle')" :description="t('evidence.emptyDescription')" />
            <PaginationBar
              :total="packetTotal"
              :limit="packetLimit"
              :offset="packetOffset"
              :loading="packetsLoading"
              @change="changePacketPage"
            />
          </div>
        </BaseSection>

        <BaseSection :title="t('evidence.detailTitle')" :description="selectedPacket ? selectedPacket.id : t('evidence.detailDescription')">
          <div v-if="selectedPacket" class="detail-grid">
            <section class="detail-card">
              <h3>{{ selectedPacket.packet_name }}</h3>
              <p>{{ selectedPacket.storage_uri }}</p>
              <div class="summary-grid">
                <span>{{ t('evidence.datasetCount', { count: Number(manifestSummary(selectedPacket).dataset_count ?? 0) }) }}</span>
                <span>{{ t('evidence.signalCount', { count: Number(manifestSummary(selectedPacket).signal_count ?? 0) }) }}</span>
                <span>{{ t('evidence.entityCount', { count: Number(manifestSummary(selectedPacket).entity_count ?? 0) }) }}</span>
                <span>{{ t('evidence.noteCount', { count: Number(manifestSummary(selectedPacket).note_count ?? 0) }) }}</span>
              </div>
            </section>

            <section class="detail-section">
              <h3>{{ t('evidence.sourceRecords') }}</h3>
              <article v-for="(item, index) in sourceRecords(selectedPacket)" :key="index" class="compact-item">
                <strong>{{ item.source_type }} · {{ item.dataset_id || item.signal_id }}</strong>
                <span>{{ item.dataset_name || item.summary || '-' }}</span>
              </article>
              <EmptyState v-if="!sourceRecords(selectedPacket).length" :title="t('evidence.noSourceRecords')" />
            </section>

            <section class="detail-section manifest-json">
              <h3>Manifest JSON</h3>
              <pre>{{ JSON.stringify(selectedPacket.manifest_json, null, 2) }}</pre>
            </section>
          </div>
          <EmptyState v-else :title="t('evidence.noSelectionTitle')" :description="t('evidence.noSelectionDescription')" />
        </BaseSection>
      </main>
    </div>
  </section>
</template>

<style scoped>
.page-grid,
.evidence-form,
.packet-list,
.detail-section {
  display: grid;
  gap: 18px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.split-grid,
.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
}

.evidence-workspace {
  display: grid;
  grid-template-columns: minmax(320px, 390px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.evidence-side-panel {
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

.evidence-main-panel {
  min-width: 0;
  display: grid;
  gap: 18px;
}

.evidence-side-panel .actions {
  display: grid;
}

.evidence-side-panel .primary-button,
.evidence-side-panel .secondary-button {
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
.packet-main p,
.detail-card p,
.compact-item span {
  color: #64748b;
}

.stat-card strong {
  display: block;
  margin-top: 6px;
  font-size: 24px;
  overflow-wrap: anywhere;
}

.section-head {
  margin-bottom: 16px;
}

.section-head h2,
.detail-card h3,
.detail-section h3 {
  margin: 0 0 6px;
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

.packet-item,
.detail-card,
.compact-item {
  padding: 16px;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(248, 250, 252, 0.82);
}

.packet-main {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.packet-main strong,
.compact-item strong {
  display: block;
  margin-bottom: 4px;
}

.packet-main p,
.detail-card p {
  margin: 0;
}

.packet-id {
  color: #2563eb;
  font-size: 12px;
  font-weight: 800;
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

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}

.summary-grid span {
  border-radius: 12px;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.86);
  font-weight: 700;
}

.manifest-json {
  grid-column: 1 / -1;
}

pre {
  margin: 0;
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

  .evidence-workspace {
    grid-template-columns: 1fr;
  }

  .evidence-side-panel {
    position: static;
    max-height: none;
    overflow: visible;
    padding-right: 0;
  }

  .split-grid,
  .detail-grid,
  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
