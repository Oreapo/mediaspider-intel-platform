<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  deleteEvidencePacket,
  evidenceDownloadUrl,
  generateEvidencePacket,
  getEvidencePacket,
} from '../api/evidence'
import { useCases } from '../composables/useCases'
import { useEvidencePackets } from '../composables/useEvidencePackets'
import type { EvidencePacket } from '../types'

const {
  items: packetItems,
  isLoading: packetsLoading,
  error: packetsError,
  fetchItems: fetchPackets,
} = useEvidencePackets()
const { items: caseItems } = useCases()

const form = ref({
  case_id: '',
  packet_name: '',
})
const selectedPacket = ref<EvidencePacket | null>(null)
const busy = ref(false)
const message = ref('')
const error = ref('')

const packetStats = computed(() => [
  { label: 'Packets', value: packetItems.value.length },
  { label: 'Cases', value: new Set(packetItems.value.map((item) => item.case_id)).size },
  { label: 'With Artifact', value: packetItems.value.filter((item) => item.storage_uri).length },
  { label: 'Latest', value: packetItems.value[0]?.packet_name || '-' },
])

function manifestSummary(packet: EvidencePacket | null) {
  const summary = packet?.manifest_json.summary
  return summary && typeof summary === 'object' ? (summary as Record<string, unknown>) : {}
}

function sourceRecords(packet: EvidencePacket | null) {
  const records = packet?.manifest_json.source_records
  return Array.isArray(records) ? (records as Array<Record<string, unknown>>) : []
}

async function submitPacket() {
  busy.value = true
  message.value = ''
  error.value = ''
  try {
    const packet = await generateEvidencePacket({
      case_id: form.value.case_id,
      packet_name: form.value.packet_name,
    })
    message.value = 'Evidence packet generated.'
    form.value.packet_name = ''
    await fetchPackets()
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

async function removePacket(packetId: string) {
  message.value = ''
  error.value = ''
  try {
    await deleteEvidencePacket(packetId, true)
    message.value = 'Evidence packet deleted.'
    if (selectedPacket.value?.id === packetId) selectedPacket.value = null
    await fetchPackets()
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

    <div class="split-grid">
      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Generate Packet</h2>
            <p>从案件当前挂接对象生成证据 manifest，并写出可下载 JSON 产物。</p>
          </div>
        </div>

        <form class="evidence-form" @submit.prevent="submitPacket">
          <label class="field">
            <span>Case</span>
            <select v-model="form.case_id" required>
              <option value="" disabled>选择案件</option>
              <option v-for="item in caseItems" :key="item.id" :value="item.id">
                {{ item.case_name }} · {{ item.status }} · {{ item.priority }}
              </option>
            </select>
          </label>

          <label class="field">
            <span>Packet Name</span>
            <input v-model="form.packet_name" required placeholder="例：导流链路证据包 2026-04-28" />
          </label>

          <div class="actions">
            <button class="primary-button" :disabled="busy" type="submit">
              {{ busy ? 'Generating...' : 'Generate Evidence Packet' }}
            </button>
          </div>
        </form>
      </section>

      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Packet Registry</h2>
            <p>已生成证据包会保留 metadata、manifest 和下载产物路径。</p>
          </div>
        </div>

        <div v-if="packetsLoading" class="muted">Loading evidence packets...</div>
        <div v-else-if="packetsError" class="error-text">{{ packetsError }}</div>
        <div v-else class="packet-list">
          <article v-for="item in packetItems" :key="item.id" class="packet-item">
            <div class="packet-main">
              <div>
                <strong>{{ item.packet_name }}</strong>
                <p>{{ item.case_id }} · {{ item.storage_uri }}</p>
              </div>
              <span class="packet-id">{{ item.id }}</span>
            </div>
            <div class="actions">
              <button class="secondary-button" type="button" @click="inspectPacket(item.id)">Inspect</button>
              <a class="secondary-button" :href="evidenceDownloadUrl(item.id)" target="_blank">Download</a>
              <button class="secondary-button destructive" type="button" @click="removePacket(item.id)">Delete</button>
            </div>
          </article>
          <div v-if="!packetItems.length" class="muted">No evidence packets yet.</div>
        </div>
      </section>
    </div>

    <div v-if="message" class="success-text">{{ message }}</div>
    <div v-if="error" class="error-text">{{ error }}</div>

    <section class="surface section-card">
      <div class="section-head">
        <div>
          <h2>Manifest Detail</h2>
          <p>{{ selectedPacket ? selectedPacket.id : '选择一个证据包查看 manifest 摘要。' }}</p>
        </div>
      </div>

      <div v-if="selectedPacket" class="detail-grid">
        <section class="detail-card">
          <h3>{{ selectedPacket.packet_name }}</h3>
          <p>{{ selectedPacket.storage_uri }}</p>
          <div class="summary-grid">
            <span>Datasets: {{ manifestSummary(selectedPacket).dataset_count ?? 0 }}</span>
            <span>Signals: {{ manifestSummary(selectedPacket).signal_count ?? 0 }}</span>
            <span>Entities: {{ manifestSummary(selectedPacket).entity_count ?? 0 }}</span>
            <span>Notes: {{ manifestSummary(selectedPacket).note_count ?? 0 }}</span>
          </div>
        </section>

        <section class="detail-section">
          <h3>Source Records</h3>
          <article v-for="(item, index) in sourceRecords(selectedPacket)" :key="index" class="compact-item">
            <strong>{{ item.source_type }} · {{ item.dataset_id || item.signal_id }}</strong>
            <span>{{ item.dataset_name || item.summary || '-' }}</span>
          </article>
          <div v-if="!sourceRecords(selectedPacket).length" class="muted">No source records.</div>
        </section>

        <section class="detail-section manifest-json">
          <h3>Manifest JSON</h3>
          <pre>{{ JSON.stringify(selectedPacket.manifest_json, null, 2) }}</pre>
        </section>
      </div>
      <div v-else class="muted">No packet selected.</div>
    </section>
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

  .split-grid,
  .detail-grid,
  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
