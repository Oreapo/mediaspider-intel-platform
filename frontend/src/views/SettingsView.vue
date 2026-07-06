<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  createPlatformProfile,
  deletePlatformProfile,
  diagnosePlatformProfile,
  updatePlatformProfile,
} from '../api/platforms'
import {
  createNotificationRule,
  deleteNotificationRule,
  markAllNotificationInboxRead,
  retryNotificationDelivery,
  runScheduledNotifications,
  updateNotificationInboxItem,
  updateNotificationRule,
} from '../api/notifications'
import AppAlert from '../components/ui/AppAlert.vue'
import AppSelect from '../components/ui/AppSelect.vue'
import PlatformLogo from '../components/ui/PlatformLogo.vue'
import FieldError from '../components/ui/FieldError.vue'
import LoadingState from '../components/ui/LoadingState.vue'
import PaginationBar from '../components/ui/PaginationBar.vue'
import PermissionGate from '../components/ui/PermissionGate.vue'
import { useI18n } from '../composables/useI18n'
import { parseList } from '../lib/list'
import { enumLabel as labelValue } from '../composables/useEnumLabel'
import { useNotifications } from '../composables/useNotifications'
import { usePlatformModels } from '../composables/usePlatformModels'
import { usePlatformProfiles } from '../composables/usePlatformProfiles'
import { requestConfirm } from '../lib/confirm'
import {
  httpUrl,
  nonNegativeNumber,
  parseJsonObject,
  required,
  type ValidationErrors,
} from '../lib/validation'
import type { PlatformProfileDiagnostics } from '../types'

const { t } = useI18n()
const {
  rules,
  deliveries,
  deliveryTotal,
  deliveryQuery,
  inbox,
  inboxTotal,
  inboxQuery,
  unreadCount,
  isLoading,
  error: loadError,
  fetchItems,
  updateDeliveryQuery,
  updateInboxQuery,
} = useNotifications()
const {
  profiles,
  isLoading: profilesLoading,
  error: profilesLoadError,
  fetchProfiles,
} = usePlatformProfiles()
const {
  items: platformModels,
  isLoading: platformModelsLoading,
  error: platformModelsError,
} = usePlatformModels()

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
  smtp_host: '',
  smtp_port: 587,
  smtp_from: '',
  smtp_username: '',
  smtp_password: '',
  smtp_use_tls: true,
  smtp_timeout_seconds: 10,
  webhook_url: '',
})
const profileForm = ref({
  platform: 'xhs',
  profile_name: '',
  auth_type: 'cookie',
  credentials_ref: '',
  settings_json: '{"headless": true}',
})
const busy = ref(false)
const message = ref('')
const error = ref('')
const profileErrors = ref<ValidationErrors>({})
const ruleErrors = ref<ValidationErrors>({})
const runResult = ref<Record<string, unknown> | null>(null)
const profileDiagnostics = ref<Record<string, PlatformProfileDiagnostics>>({})
const deliveryFilters = ref({
  q: '',
  status: '',
  channel: '',
  target_type: '',
})
const inboxFilters = ref({
  q: '',
  unread_only: false,
})
const selectedChannels = computed(() => parseList(form.value.channels))
const usesEmail = computed(() => selectedChannels.value.includes('email'))
const usesWebhook = computed(() => selectedChannels.value.includes('webhook'))
const profilePlatformOptions = computed(() =>
  platformModels.value.map((item) => ({ value: item.platform, label: labelValue(item.platform) })),
)

watch(
  profilePlatformOptions,
  (options) => {
    if (!options.length) return
    if (!options.some((item) => item.value === profileForm.value.platform)) {
      profileForm.value.platform = options[0].value
    }
  },
  { immediate: true },
)

const stats = computed(() => [
  { label: t('settings.stats.rules'), value: rules.value.length },
  { label: t('settings.stats.enabled'), value: rules.value.filter((item) => item.enabled).length },
  { label: t('settings.stats.unread'), value: unreadCount.value },
  { label: t('settings.stats.deliveries'), value: deliveryTotal.value },
])

function channelConfig() {
  const config: Record<string, unknown> = {}
  const emails = parseList(form.value.email_recipients)
  if (emails.length) config.email_recipients = emails
  if (form.value.smtp_host.trim()) config.smtp_host = form.value.smtp_host.trim()
  if (form.value.smtp_port) config.smtp_port = form.value.smtp_port
  if (form.value.smtp_from.trim()) config.smtp_from = form.value.smtp_from.trim()
  if (form.value.smtp_username.trim()) config.smtp_username = form.value.smtp_username.trim()
  if (form.value.smtp_password.trim()) config.smtp_password = form.value.smtp_password
  config.smtp_use_tls = form.value.smtp_use_tls
  if (form.value.smtp_timeout_seconds) config.smtp_timeout_seconds = form.value.smtp_timeout_seconds
  if (form.value.webhook_url.trim()) config.webhook_url = form.value.webhook_url.trim()
  return config
}

function validateProfileForm() {
  const errors: ValidationErrors = {}
  const platformError = required(profileForm.value.platform, t('settings.profile.platform'))
  const nameError = required(profileForm.value.profile_name, t('settings.profile.name'))
  const settings = parseJsonObject(profileForm.value.settings_json, t('settings.profile.settingsJson'))

  if (platformError) errors.platform = platformError
  if (nameError) errors.profile_name = nameError
  if (settings.error) errors.settings_json = settings.error

  profileErrors.value = errors
  return {
    isValid: Object.keys(errors).length === 0,
    settingsJson: settings.value || {},
  }
}

function validateRuleForm() {
  const errors: ValidationErrors = {}
  const nameError = required(form.value.rule_name, t('settings.rule.name'))
  const cronError = required(form.value.cron_expr, t('settings.rule.cron'))
  const channels = parseList(form.value.channels)
  const channelError = channels.length ? '' : t('settings.rule.channelRequired')
  const cooldownError = nonNegativeNumber(form.value.cooldown_minutes, t('settings.rule.cooldown'))
  const webhookError = usesWebhook.value ? httpUrl(form.value.webhook_url, t('settings.rule.webhookUrl')) : ''
  const smtpPortError = usesEmail.value ? nonNegativeNumber(form.value.smtp_port, t('settings.rule.smtpPort')) : ''
  const smtpTimeoutError = usesEmail.value
    ? nonNegativeNumber(form.value.smtp_timeout_seconds, t('settings.rule.smtpTimeout'))
    : ''

  if (nameError) errors.rule_name = nameError
  if (cronError) errors.cron_expr = cronError
  if (channelError) errors.channels = channelError
  if (cooldownError) errors.cooldown_minutes = cooldownError
  if (webhookError) errors.webhook_url = webhookError
  if (usesEmail.value) {
    const recipientsError = required(form.value.email_recipients, t('settings.rule.emailRecipients'))
    const smtpHostError = required(form.value.smtp_host, t('settings.rule.smtpHost'))
    const smtpFromError = required(form.value.smtp_from, t('settings.rule.smtpFrom'))
    if (recipientsError) errors.email_recipients = recipientsError
    if (smtpHostError) errors.smtp_host = smtpHostError
    if (smtpFromError) errors.smtp_from = smtpFromError
    if (smtpPortError) errors.smtp_port = smtpPortError
    if (smtpTimeoutError) errors.smtp_timeout_seconds = smtpTimeoutError
  }

  ruleErrors.value = errors
  return Object.keys(errors).length === 0
}

async function submitProfile() {
  message.value = ''
  error.value = ''
  const validation = validateProfileForm()
  if (!validation.isValid) {
    error.value = t('settings.profile.fixErrors')
    return
  }

  busy.value = true
  try {
    await createPlatformProfile({
      platform: profileForm.value.platform,
      profile_name: profileForm.value.profile_name,
      auth_type: profileForm.value.auth_type,
      credentials_ref: profileForm.value.credentials_ref,
      settings_json: validation.settingsJson,
    })
    message.value = t('settings.profile.created')
    profileForm.value.profile_name = ''
    profileForm.value.credentials_ref = ''
    await fetchProfiles()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function rotateProfile(profileId: string) {
  const nextValue = window.prompt(t('settings.profile.rotatePrompt'))
  if (!nextValue) return
  message.value = ''
  error.value = ''
  try {
    await updatePlatformProfile(profileId, { credentials_ref: nextValue })
    message.value = t('settings.profile.updatedCredentials')
    await fetchProfiles()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function inspectProfile(profileId: string) {
  message.value = ''
  error.value = ''
  try {
    profileDiagnostics.value = {
      ...profileDiagnostics.value,
      [profileId]: await diagnosePlatformProfile(profileId),
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function removeProfile(profileId: string) {
  const confirmed = await requestConfirm({
    title: t('settings.profile.deleteTitle'),
    message: t('settings.profile.deleteMessage'),
    confirmLabel: t('settings.profile.deleteConfirm'),
  })
  if (!confirmed) return

  message.value = ''
  error.value = ''
  try {
    await deletePlatformProfile(profileId)
    const { [profileId]: _removed, ...rest } = profileDiagnostics.value
    profileDiagnostics.value = rest
    message.value = t('settings.profile.deleted')
    await fetchProfiles()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function submitRule() {
  message.value = ''
  error.value = ''
  if (!validateRuleForm()) {
    error.value = t('settings.rule.fixErrors')
    return
  }

  busy.value = true
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
    message.value = t('settings.rule.created')
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
    message.value = enabled ? t('settings.rule.enabledMessage') : t('settings.rule.disabledMessage')
    await fetchItems()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function removeRule(ruleId: string) {
  const confirmed = await requestConfirm({
    title: t('settings.rule.deleteTitle'),
    message: t('settings.rule.deleteMessage'),
    confirmLabel: t('settings.rule.deleteConfirm'),
  })
  if (!confirmed) return

  message.value = ''
  error.value = ''
  try {
    await deleteNotificationRule(ruleId)
    message.value = t('settings.rule.deleted')
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
    message.value = t('settings.rule.scheduledRunComplete')
    await fetchItems()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function applyDeliveryFilters() {
  await updateDeliveryQuery({
    ...deliveryFilters.value,
    limit: 20,
    offset: 0,
  })
}

async function resetDeliveryFilters() {
  deliveryFilters.value = {
    q: '',
    status: '',
    channel: '',
    target_type: '',
  }
  await updateDeliveryQuery({ limit: 20, offset: 0, q: '', status: '', channel: '', target_type: '' })
}

async function moveDeliveryPage(offset: number) {
  await updateDeliveryQuery({ offset })
}

async function retryDelivery(deliveryId: string) {
  message.value = ''
  error.value = ''
  busy.value = true
  try {
    const delivery = await retryNotificationDelivery(deliveryId)
    message.value =
      delivery.status === 'sent' ? t('settings.delivery.retrySucceeded') : t('settings.delivery.retryFailed')
    await fetchItems()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    busy.value = false
  }
}

async function applyInboxFilters() {
  await updateInboxQuery({
    ...inboxFilters.value,
    limit: 20,
    offset: 0,
  })
}

async function toggleInboxRead(deliveryId: string, read: boolean) {
  message.value = ''
  error.value = ''
  try {
    await updateNotificationInboxItem(deliveryId, read)
    message.value = read ? t('settings.inbox.markedRead') : t('settings.inbox.markedUnread')
    await fetchItems()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function markAllRead() {
  message.value = ''
  error.value = ''
  try {
    const result = await markAllNotificationInboxRead()
    message.value = t('settings.inbox.markAllReadResult', { count: result.updated_count })
    await fetchItems()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function moveInboxPage(offset: number) {
  await updateInboxQuery({ offset })
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

    <div class="settings-workspace">
      <aside class="settings-side-panel">
      <section class="surface section-card settings-side-card">
        <div class="section-head">
          <div>
            <h2>{{ t('settings.profile.title') }}</h2>
            <p>{{ t('settings.profile.description') }}</p>
          </div>
        </div>

        <AppAlert v-if="platformModelsError" tone="error" :title="t('settings.profile.platformLoadFailed')" :message="platformModelsError" />
        <PermissionGate area="operations">
        <form class="settings-form" @submit.prevent="submitProfile">
          <div class="grid-two">
            <label class="field">
              <span>{{ t('settings.profile.platform') }}</span>
              <AppSelect
                v-model="profileForm.platform"
                :disabled="platformModelsLoading && !profilePlatformOptions.length"
                :options="profilePlatformOptions.map((option) => ({ ...option, platform: String(option.value) }))"
              />
              <FieldError :message="profileErrors.platform" />
            </label>
            <label class="field">
              <span>{{ t('settings.profile.authType') }}</span>
              <AppSelect
                v-model="profileForm.auth_type"
                :options="[
                  { value: 'cookie', label: 'cookie' },
                  { value: 'qrcode', label: 'qrcode' },
                  { value: 'phone', label: 'phone' },
                ]"
              />
            </label>
          </div>

          <label class="field">
            <span>{{ t('settings.profile.name') }}</span>
            <input v-model="profileForm.profile_name" required :placeholder="t('settings.profile.namePlaceholder')" />
            <FieldError :message="profileErrors.profile_name" />
          </label>

          <label class="field">
            <span>credentials_ref</span>
            <textarea v-model="profileForm.credentials_ref" rows="3" :placeholder="t('settings.profile.credentialsPlaceholder')"></textarea>
          </label>

          <label class="field">
            <span>{{ t('settings.profile.settingsJson') }}</span>
            <textarea v-model="profileForm.settings_json" rows="4" placeholder='{"headless": true}'></textarea>
            <FieldError :message="profileErrors.settings_json" />
          </label>

          <div class="actions">
            <button class="primary-button" :disabled="busy" type="submit">
              {{ busy ? t('common.saving') : t('settings.profile.create') }}
            </button>
          </div>
        </form>
        </PermissionGate>
      </section>

      <section class="surface section-card settings-side-card">
        <div class="section-head">
          <div>
            <h2>{{ t('settings.rule.title') }}</h2>
            <p>{{ t('settings.rule.description') }}</p>
          </div>
        </div>

        <PermissionGate area="operations">
        <form class="settings-form" @submit.prevent="submitRule">
          <label class="field">
            <span>{{ t('settings.rule.name') }}</span>
            <input v-model="form.rule_name" required :placeholder="t('settings.rule.namePlaceholder')" />
            <FieldError :message="ruleErrors.rule_name" />
          </label>

          <div class="grid-two">
            <label class="field">
              <span>{{ t('settings.rule.riskThreshold') }}</span>
              <AppSelect
                v-model="form.risk_level_threshold"
                :options="[
                  { value: 'low', label: 'low' },
                  { value: 'medium', label: 'medium' },
                  { value: 'high', label: 'high' },
                  { value: 'critical', label: 'critical' },
                ]"
              />
            </label>
            <label class="field">
              <span>{{ t('settings.rule.cron') }}</span>
              <input v-model="form.cron_expr" required placeholder="*/30 * * * *" />
              <FieldError :message="ruleErrors.cron_expr" />
            </label>
          </div>

          <div class="grid-two">
            <label class="field">
              <span>{{ t('settings.rule.scenarios') }}</span>
              <input v-model="form.scenario_types" placeholder="lead_diversion,seller_risk" />
            </label>
            <label class="field">
              <span>{{ t('settings.rule.platforms') }}</span>
              <input v-model="form.platforms" placeholder="xhs,dy,xianyu" />
            </label>
          </div>

          <div class="grid-two">
            <label class="field">
              <span>{{ t('settings.rule.channels') }}</span>
              <input v-model="form.channels" required placeholder="internal_inbox,email,webhook" />
              <FieldError :message="ruleErrors.channels" />
            </label>
            <label class="field">
              <span>{{ t('settings.rule.cooldown') }}</span>
              <input v-model.number="form.cooldown_minutes" min="0" step="1" type="number" />
              <FieldError :message="ruleErrors.cooldown_minutes" />
            </label>
          </div>

          <div v-if="usesEmail" class="channel-config">
            <h3>{{ t('settings.rule.emailChannel') }}</h3>
            <div class="grid-two">
              <label class="field">
                <span>{{ t('settings.rule.emailRecipients') }}</span>
                <input v-model="form.email_recipients" placeholder="risk@example.com,ops@example.com" />
                <FieldError :message="ruleErrors.email_recipients" />
              </label>
              <label class="field">
                <span>{{ t('settings.rule.smtpHost') }}</span>
                <input v-model="form.smtp_host" placeholder="smtp.example.com" />
                <FieldError :message="ruleErrors.smtp_host" />
              </label>
            </div>
            <div class="grid-two">
              <label class="field">
                <span>{{ t('settings.rule.smtpPort') }}</span>
                <input v-model.number="form.smtp_port" min="1" step="1" type="number" />
                <FieldError :message="ruleErrors.smtp_port" />
              </label>
              <label class="field">
                <span>{{ t('settings.rule.smtpFrom') }}</span>
                <input v-model="form.smtp_from" placeholder="platform@example.com" />
                <FieldError :message="ruleErrors.smtp_from" />
              </label>
            </div>
            <div class="grid-two">
              <label class="field">
                <span>{{ t('settings.rule.smtpUsername') }}</span>
                <input v-model="form.smtp_username" :placeholder="t('common.optional')" />
              </label>
              <label class="field">
                <span>{{ t('settings.rule.smtpPassword') }}</span>
                <input v-model="form.smtp_password" autocomplete="new-password" :placeholder="t('common.optional')" type="password" />
              </label>
            </div>
            <div class="grid-two">
              <label class="field">
                <span>{{ t('settings.rule.smtpTimeout') }}</span>
                <input v-model.number="form.smtp_timeout_seconds" min="1" step="1" type="number" />
                <FieldError :message="ruleErrors.smtp_timeout_seconds" />
              </label>
              <label class="toggle-line channel-toggle">
                <input v-model="form.smtp_use_tls" type="checkbox" />
                <span>{{ t('settings.rule.enableStarttls') }}</span>
              </label>
            </div>
          </div>

          <div v-if="usesWebhook" class="channel-config">
            <h3>{{ t('settings.rule.webhookChannel') }}</h3>
            <label class="field">
              <span>{{ t('settings.rule.webhookUrl') }}</span>
              <input v-model="form.webhook_url" placeholder="https://example.test/webhook" />
              <FieldError :message="ruleErrors.webhook_url" />
            </label>
          </div>

          <label class="toggle-line">
            <input v-model="form.enabled" type="checkbox" />
            <span>{{ t('common.enabled') }}</span>
          </label>

          <div class="actions">
            <button class="primary-button" :disabled="busy" type="submit">
              {{ busy ? t('common.saving') : t('settings.rule.create') }}
            </button>
            <button class="secondary-button" :disabled="busy" type="button" @click="runNow">
              {{ t('settings.rule.runScheduledNow') }}
            </button>
          </div>
        </form>
        </PermissionGate>
      </section>

      <AppAlert v-if="message" tone="success" :title="t('common.operationSucceeded')" :message="message" />
      <AppAlert v-if="error" tone="error" :title="t('common.operationFailed')" :message="error" />
      </aside>

      <main class="settings-main-panel">
      <div class="split-grid">
      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>{{ t('settings.profile.listTitle') }}</h2>
            <p>{{ t('settings.profile.listDescription') }}</p>
          </div>
        </div>

        <LoadingState v-if="profilesLoading" :title="t('settings.profile.loading')" />
        <AppAlert v-else-if="profilesLoadError" tone="error" :title="t('common.loadFailed')" :message="profilesLoadError" />
        <div v-else class="item-list">
          <article v-for="profile in profiles" :key="profile.id" class="list-item">
            <div class="item-main">
              <div>
                <strong>{{ profile.profile_name }}</strong>
                <p class="platform-line">
                  <PlatformLogo :platform="profile.platform" :size="16" />
                  {{ labelValue(profile.platform) }} · {{ labelValue(profile.auth_type) }} · {{ profile.id }}
                </p>
              </div>
              <span class="status-badge">{{ profile.credentials_ref ? t('settings.profile.configured') : t('settings.profile.pendingConfig') }}</span>
            </div>
            <div class="item-meta">
              <span>{{ t('settings.profile.credentials') }}: {{ profile.credentials_ref || '-' }}</span>
              <span>{{ t('common.updated') }}: {{ profile.updated_at }}</span>
            </div>
            <div class="actions">
              <PermissionGate area="operations" compact>
              <button class="secondary-button" type="button" @click="inspectProfile(profile.id)">{{ t('settings.profile.diagnose') }}</button>
              <button class="secondary-button" type="button" @click="rotateProfile(profile.id)">{{ t('settings.profile.updateCredentials') }}</button>
              <button class="secondary-button destructive" type="button" @click="removeProfile(profile.id)">{{ t('common.delete') }}</button>
              </PermissionGate>
            </div>
            <pre v-if="profileDiagnostics[profile.id]">{{ JSON.stringify(profileDiagnostics[profile.id], null, 2) }}</pre>
          </article>
          <div v-if="!profiles.length" class="muted">{{ t('settings.profile.empty') }}</div>
        </div>
      </section>

      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>{{ t('settings.rule.listTitle') }}</h2>
            <p>{{ t('settings.rule.listDescription') }}</p>
          </div>
        </div>

        <LoadingState v-if="isLoading" :title="t('settings.rule.loading')" />
        <AppAlert v-else-if="loadError" tone="error" :title="t('common.loadFailed')" :message="loadError" />
        <div v-else class="item-list">
          <article v-for="item in rules" :key="item.id" class="list-item">
            <div class="item-main">
              <div>
                <strong>{{ item.rule_name }}</strong>
                <p>{{ item.event_type }} · {{ item.cron_expr }} · {{ item.risk_level_threshold }}</p>
              </div>
              <span class="status-badge" :class="{ disabled: !item.enabled }">
                {{ item.enabled ? t('enum.enabled') : t('enum.disabled') }}
              </span>
            </div>
            <div class="item-meta">
              <span>{{ t('settings.rule.channels') }}: {{ item.channels.join(', ') }}</span>
              <span>{{ t('settings.rule.lastExecuted') }}: {{ item.last_executed_at || '-' }}</span>
            </div>
            <div class="actions">
              <PermissionGate area="operations" compact>
              <button class="secondary-button" type="button" @click="toggleRule(item.id, !item.enabled)">
                {{ item.enabled ? t('common.disable') : t('common.enable') }}
              </button>
              <button class="secondary-button destructive" type="button" @click="removeRule(item.id)">{{ t('common.delete') }}</button>
              </PermissionGate>
            </div>
          </article>
          <div v-if="!rules.length" class="muted">{{ t('settings.rule.empty') }}</div>
        </div>
      </section>
    </div>

    <section class="surface section-card">
      <div class="section-head section-head-inline">
        <div>
          <h2>{{ t('settings.inbox.title') }}</h2>
          <p>{{ t('settings.inbox.description') }}</p>
        </div>
        <PermissionGate area="workflow" compact>
          <button class="secondary-button" type="button" @click="markAllRead">{{ t('settings.inbox.markAllRead') }}</button>
        </PermissionGate>
      </div>

      <form class="filter-bar inbox-filter" @submit.prevent="applyInboxFilters">
        <input v-model="inboxFilters.q" :placeholder="t('settings.inbox.searchPlaceholder')" />
        <label class="toggle-line">
          <input v-model="inboxFilters.unread_only" type="checkbox" />
          <span>{{ t('settings.inbox.unreadOnly') }}</span>
        </label>
        <button class="secondary-button" :disabled="busy" type="submit">{{ t('common.filter') }}</button>
      </form>

      <LoadingState v-if="isLoading" :title="t('settings.inbox.loading')" />
      <div v-else class="inbox-list">
        <article v-for="item in inbox" :key="item.id" class="inbox-item" :class="{ unread: !item.read }">
          <div class="item-main">
            <div>
              <strong>{{ item.title }}</strong>
              <p>{{ item.rule_name || item.rule_id }} · {{ item.target_type }} · {{ item.created_at }}</p>
            </div>
            <span class="status-badge" :class="{ skipped: item.read }">{{ item.read ? t('settings.inbox.read') : t('settings.inbox.unread') }}</span>
          </div>
          <div class="item-meta">
            <span>{{ item.summary || t('settings.inbox.noSummary') }}</span>
            <span>{{ t('settings.inbox.eventTarget', { count: item.event_count, targetId: item.target_id }) }}</span>
          </div>
          <div class="actions">
            <PermissionGate area="workflow" compact>
            <button class="secondary-button" type="button" @click="toggleInboxRead(item.id, !item.read)">
              {{ item.read ? t('settings.inbox.markUnread') : t('settings.inbox.markRead') }}
            </button>
            </PermissionGate>
          </div>
        </article>
        <div v-if="!inbox.length" class="muted">{{ t('settings.inbox.empty') }}</div>
      </div>

      <PaginationBar
        :total="inboxTotal"
        :limit="inboxQuery.limit || 20"
        :offset="inboxQuery.offset || 0"
        :loading="isLoading"
        @change="moveInboxPage"
      />
    </section>

    <div class="split-grid">
      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>{{ t('settings.delivery.title') }}</h2>
            <p>{{ t('settings.delivery.description') }}</p>
          </div>
        </div>

        <form class="filter-bar" @submit.prevent="applyDeliveryFilters">
          <input v-model="deliveryFilters.q" :placeholder="t('settings.delivery.searchPlaceholder')" />
          <AppSelect
            v-model="deliveryFilters.status"
            :options="[
              { value: '', label: t('settings.delivery.allStatuses') },
              { value: 'sent', label: t('enum.sent') },
              { value: 'failed', label: t('enum.failed') },
              { value: 'skipped', label: t('enum.skipped') },
            ]"
          />
          <AppSelect
            v-model="deliveryFilters.channel"
            :options="[
              { value: '', label: t('settings.delivery.allChannels') },
              { value: 'internal_inbox', label: 'internal_inbox' },
              { value: 'email', label: 'email' },
              { value: 'webhook', label: 'webhook' },
            ]"
          />
          <AppSelect
            v-model="deliveryFilters.target_type"
            :options="[
              { value: '', label: t('settings.delivery.allTargets') },
              { value: 'signal', label: 'signal' },
              { value: 'case', label: 'case' },
              { value: 'evidence_packet', label: 'evidence_packet' },
              { value: 'scheduled_digest', label: 'scheduled_digest' },
            ]"
          />
          <button class="secondary-button" :disabled="busy" type="submit">{{ t('common.filter') }}</button>
          <button class="secondary-button" :disabled="busy" type="button" @click="resetDeliveryFilters">{{ t('common.reset') }}</button>
        </form>

        <div class="item-list">
          <article v-for="item in deliveries" :key="item.id" class="list-item">
            <div class="item-main">
              <div>
                <strong>{{ item.target_type }} · {{ item.target_id }}</strong>
                <p>{{ item.channel }} · {{ item.created_at }}</p>
              </div>
              <span class="status-badge" :class="item.status">{{ labelValue(item.status) }}</span>
            </div>
            <div v-if="item.error_message" class="error-text">{{ item.error_message }}</div>
            <div class="item-meta">
              <span>{{ t('settings.delivery.retryCount') }}: {{ item.retry_count }}</span>
              <span>{{ t('settings.delivery.lastAttempt') }}: {{ item.last_attempt_at || '-' }}</span>
            </div>
            <div v-if="item.status === 'failed'" class="actions">
              <PermissionGate area="operations" compact>
              <button class="secondary-button" :disabled="busy" type="button" @click="retryDelivery(item.id)">{{ t('settings.delivery.retry') }}</button>
              </PermissionGate>
            </div>
          </article>
          <div v-if="!deliveries.length" class="muted">{{ t('settings.delivery.empty') }}</div>
        </div>

        <PaginationBar
          :total="deliveryTotal"
          :limit="deliveryQuery.limit || 20"
          :offset="deliveryQuery.offset || 0"
          :loading="isLoading"
          @change="moveDeliveryPage"
        />
      </section>

      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>{{ t('settings.runResult.title') }}</h2>
            <p>{{ t('settings.runResult.description') }}</p>
          </div>
        </div>
        <pre v-if="runResult">{{ JSON.stringify(runResult, null, 2) }}</pre>
        <div v-else class="muted">{{ t('settings.runResult.empty') }}</div>
      </section>
    </div>
      </main>
    </div>
  </section>
</template>

<style scoped>
.page-grid,
.settings-form,
.item-list {
  display: grid;
  gap: 16px;
}

.filter-bar {
  display: grid;
  grid-template-columns: minmax(220px, 1.6fr) repeat(3, minmax(132px, 1fr)) auto auto;
  gap: 10px;
  margin-bottom: 16px;
  align-items: center;
}

.inbox-filter {
  grid-template-columns: minmax(220px, 1fr) auto auto;
  align-items: center;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.split-grid {
  display: grid;
  grid-template-columns: minmax(480px, 0.95fr) minmax(460px, 1.05fr);
  gap: 16px;
  align-items: start;
}

.settings-workspace {
  display: grid;
  grid-template-columns: minmax(320px, 390px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.settings-side-panel {
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

.settings-main-panel {
  min-width: 0;
  display: grid;
  gap: 16px;
}

.settings-side-panel .grid-two,
.settings-side-panel .filter-bar {
  grid-template-columns: 1fr;
}

.settings-side-panel .actions {
  display: grid;
}

.settings-side-panel .primary-button,
.settings-side-panel .secondary-button {
  width: 100%;
}

.section-card,
.stat-card {
  overflow: hidden;
  border-radius: var(--radius);
  padding: 20px;
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
  font-size: 32px;
  line-height: 1;
}

.section-head {
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid rgba(215, 224, 234, 0.7);
}

.section-head-inline {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.section-head h2 {
  margin: 0 0 6px;
  font-size: 20px;
}

.grid-two {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.channel-config {
  display: grid;
  gap: 12px;
  padding-top: 14px;
  border-top: 1px solid rgba(215, 224, 234, 0.7);
}

.channel-config h3 {
  margin: 0;
  font-size: 15px;
}

.field {
  display: grid;
  gap: 8px;
}

.field span {
  font-size: 12px;
  font-weight: 700;
  color: var(--muted-foreground);
}

.field input,
.field select,
.field textarea,
.filter-bar input,
.filter-bar select {
  width: 100%;
  min-height: 44px;
  padding: 11px 13px;
  border-radius: var(--radius);
  border: 1px solid rgba(203, 213, 225, 0.95);
  background: rgba(255, 255, 255, 0.94);
}

.field textarea {
  resize: vertical;
  min-height: 86px;
}

.platform-line {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.toggle-line {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #334155;
  font-weight: 700;
}

.channel-toggle {
  min-height: 44px;
  align-self: end;
}

.toggle-line input {
  width: 16px;
  height: 16px;
  accent-color: color-mix(in oklch, var(--accent) 70%, var(--primary));
}

.list-item {
  padding: 15px;
  border-radius: var(--radius);
  border: 1px solid rgba(215, 224, 234, 0.84);
  background: rgba(248, 250, 252, 0.74);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.86) inset;
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
  border-radius: var(--radius);
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

.inbox-list {
  display: grid;
  gap: 12px;
}

.inbox-item {
  padding: 15px;
  border-radius: var(--radius);
  border: 1px solid rgba(215, 224, 234, 0.84);
  background: rgba(248, 250, 252, 0.76);
}

.inbox-item.unread {
  border-color: color-mix(in oklch, var(--primary) 28%, white);
  background:
    linear-gradient(90deg, color-mix(in oklch, var(--primary) 8%, white), rgba(255, 255, 255, 0.86)),
    rgba(239, 246, 255, 0.9);
}

.primary-button,
.secondary-button {
  border: none;
  border-radius: var(--radius);
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

.secondary-button.destructive {
  background: rgba(254, 226, 226, 0.95);
  color: #b91c1c;
}

pre {
  margin: 0;
  padding: 14px;
  overflow: auto;
  border-radius: var(--radius);
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

  .settings-workspace {
    grid-template-columns: 1fr;
  }

  .settings-side-panel {
    position: static;
    max-height: none;
    overflow: visible;
    padding-right: 0;
  }

  .split-grid,
  .grid-two,
  .filter-bar,
  .inbox-filter {
    grid-template-columns: 1fr;
  }

  .section-head-inline {
    display: grid;
  }
}
</style>
