<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  createNotificationRule,
  deleteNotificationRule,
  runScheduledNotifications,
  updateNotificationRule,
} from '../api/notifications'
import { useNotifications } from '../composables/useNotifications'

const {
  rules,
  deliveries,
  isLoading,
  error: loadError,
  fetchItems,
} = useNotifications()

const form = ref({
  rule_name: '',
  enabled: true,
  risk_level_threshold: 'medium',
  scenario_types: '',
  platforms: '',
  channels: 'internal_inbox',
  cron_expr: '*/30 * * * *',
  cooldown_minutes: 60,
  email_recipients: '',
  webhook_url: '',
})
const busy = ref(false)
const message = ref('')
const error = ref('')
const runResult = ref<Record<string, unknown> | null>(null)

const stats = computed(() => [
  { label: 'Rules', value: rules.value.length },
  { label: 'Enabled', value: rules.value.filter((item) => item.enabled).length },
  { label: 'Deliveries', value: deliveries.value.length },
  { label: 'Failures', value: deliveries.value.filter((item) => item.status === 'failed').length },
])

function parseList(text: string) {
  return text
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function channelConfig() {
  const config: Record<string, unknown> = {}
  const emails = parseList(form.value.email_recipients)
  if (emails.length) config.email_recipients = emails
  if (form.value.webhook_url.trim()) config.webhook_url = form.value.webhook_url.trim()
  return config
}

async function submitRule() {
  busy.value = true
  message.value = ''
  error.value = ''
  try {
    await createNotificationRule({
      rule_name: form.value.rule_name,
      enabled: form.value.enabled,
      event_type: 'scheduled_digest',
      risk_level_threshold: form.value.risk_level_threshold,
      scenario_types: parseList(form.value.scenario_types),
      platforms: parseList(form.value.platforms),
      channels: parseList(form.value.channels),
      cron_expr: form.value.cron_expr,
      cooldown_minutes: form.value.cooldown_minutes,
      channel_config_json: channelConfig(),
    })
    message.value = 'Notification rule created.'
    form.value.rule_name = ''
    await fetchItems()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function toggleRule(ruleId: string, enabled: boolean) {
  message.value = ''
  error.value = ''
  try {
    await updateNotificationRule(ruleId, { enabled })
    message.value = enabled ? 'Rule enabled.' : 'Rule disabled.'
    await fetchItems()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function removeRule(ruleId: string) {
  message.value = ''
  error.value = ''
  try {
    await deleteNotificationRule(ruleId)
    message.value = 'Rule deleted.'
    await fetchItems()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function runNow() {
  busy.value = true
  message.value = ''
  error.value = ''
  try {
    const now = new Date()
    now.setSeconds(0, 0)
    runResult.value = await runScheduledNotifications(now.toISOString().replace('Z', ''))
    message.value = 'Scheduled digests evaluated.'
    await fetchItems()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="page-grid">
    <div class="stats-grid">
      <article v-for="stat in stats" :key="stat.label" class="surface stat-card">
        <span>{{ stat.label }}</span>
        <strong>{{ stat.value }}</strong>
      </article>
    </div>

    <div class="split-grid">
      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Notification Rule</h2>
            <p>配置 scheduled digest 规则，按风险、场景、平台和冷却时间过滤。</p>
          </div>
        </div>

        <form class="settings-form" @submit.prevent="submitRule">
          <label class="field">
            <span>Rule Name</span>
            <input v-model="form.rule_name" required placeholder="例：高风险导流日报" />
          </label>

          <div class="grid-two">
            <label class="field">
              <span>Risk Threshold</span>
              <select v-model="form.risk_level_threshold">
                <option value="low">low</option>
                <option value="medium">medium</option>
                <option value="high">high</option>
                <option value="critical">critical</option>
              </select>
            </label>
            <label class="field">
              <span>Cron</span>
              <input v-model="form.cron_expr" required placeholder="*/30 * * * *" />
            </label>
          </div>

          <div class="grid-two">
            <label class="field">
              <span>Scenarios</span>
              <input v-model="form.scenario_types" placeholder="lead_diversion,seller_risk" />
            </label>
            <label class="field">
              <span>Platforms</span>
              <input v-model="form.platforms" placeholder="xhs,dy,xianyu" />
            </label>
          </div>

          <div class="grid-two">
            <label class="field">
              <span>Channels</span>
              <input v-model="form.channels" required placeholder="internal_inbox,email,webhook" />
            </label>
            <label class="field">
              <span>Cooldown Minutes</span>
              <input v-model.number="form.cooldown_minutes" min="0" step="1" type="number" />
            </label>
          </div>

          <div class="grid-two">
            <label class="field">
              <span>Email Recipients</span>
              <input v-model="form.email_recipients" placeholder="risk@example.com,ops@example.com" />
            </label>
            <label class="field">
              <span>Webhook URL</span>
              <input v-model="form.webhook_url" placeholder="https://example.test/webhook" />
            </label>
          </div>

          <label class="toggle-line">
            <input v-model="form.enabled" type="checkbox" />
            <span>Enabled</span>
          </label>

          <div class="actions">
            <button class="primary-button" :disabled="busy" type="submit">
              {{ busy ? 'Saving...' : 'Create Rule' }}
            </button>
            <button class="secondary-button" :disabled="busy" type="button" @click="runNow">
              Run Scheduled Now
            </button>
          </div>
        </form>
      </section>

      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Rules</h2>
            <p>禁用规则不会被 cron 执行；last run 只在投递记录落库后更新。</p>
          </div>
        </div>

        <div v-if="isLoading" class="muted">Loading notification settings...</div>
        <div v-else-if="loadError" class="error-text">{{ loadError }}</div>
        <div v-else class="item-list">
          <article v-for="item in rules" :key="item.id" class="list-item">
            <div class="item-main">
              <div>
                <strong>{{ item.rule_name }}</strong>
                <p>{{ item.event_type }} · {{ item.cron_expr }} · {{ item.risk_level_threshold }}</p>
              </div>
              <span class="status-badge" :class="{ disabled: !item.enabled }">
                {{ item.enabled ? 'enabled' : 'disabled' }}
              </span>
            </div>
            <div class="item-meta">
              <span>channels: {{ item.channels.join(', ') }}</span>
              <span>last: {{ item.last_executed_at || '-' }}</span>
            </div>
            <div class="actions">
              <button class="secondary-button" type="button" @click="toggleRule(item.id, !item.enabled)">
                {{ item.enabled ? 'Disable' : 'Enable' }}
              </button>
              <button class="secondary-button destructive" type="button" @click="removeRule(item.id)">Delete</button>
            </div>
          </article>
          <div v-if="!rules.length" class="muted">No notification rules yet.</div>
        </div>
      </section>
    </div>

    <div v-if="message" class="success-text">{{ message }}</div>
    <div v-if="error" class="error-text">{{ error }}</div>

    <div class="split-grid">
      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Deliveries</h2>
            <p>每条投递记录都保留目标对象、通道、状态、payload 和错误信息。</p>
          </div>
        </div>

        <div class="item-list">
          <article v-for="item in deliveries.slice(0, 20)" :key="item.id" class="list-item">
            <div class="item-main">
              <div>
                <strong>{{ item.target_type }} · {{ item.target_id }}</strong>
                <p>{{ item.channel }} · {{ item.created_at }}</p>
              </div>
              <span class="status-badge" :class="item.status">{{ item.status }}</span>
            </div>
            <div v-if="item.error_message" class="error-text">{{ item.error_message }}</div>
          </article>
          <div v-if="!deliveries.length" class="muted">No deliveries yet.</div>
        </div>
      </section>

      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Last Run</h2>
            <p>手动运行 scheduled digest 的结果摘要。</p>
          </div>
        </div>
        <pre v-if="runResult">{{ JSON.stringify(runResult, null, 2) }}</pre>
        <div v-else class="muted">No run result loaded.</div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.page-grid,
.settings-form,
.item-list {
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
.item-main p,
.item-meta {
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

.section-head h2 {
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

.toggle-line {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #334155;
  font-weight: 700;
}

.list-item {
  padding: 16px;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(248, 250, 252, 0.82);
}

.item-main {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.item-main strong {
  display: block;
  margin-bottom: 4px;
}

.item-main p {
  margin: 0;
}

.item-meta {
  display: grid;
  gap: 4px;
  margin: 12px 0;
  font-size: 13px;
}

.status-badge {
  align-self: start;
  border-radius: 999px;
  padding: 6px 10px;
  background: rgba(22, 163, 74, 0.1);
  color: #15803d;
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

.status-badge.disabled,
.status-badge.failed {
  background: rgba(239, 68, 68, 0.12);
  color: #b91c1c;
}

.status-badge.skipped {
  background: rgba(217, 119, 6, 0.12);
  color: #b45309;
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
  .grid-two {
    grid-template-columns: 1fr;
  }
}
</style>
