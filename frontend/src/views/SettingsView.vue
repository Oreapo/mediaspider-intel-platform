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
import FieldError from '../components/ui/FieldError.vue'
import LoadingState from '../components/ui/LoadingState.vue'
import PermissionGate from '../components/ui/PermissionGate.vue'
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

const {
  rules,
  deliveries,
  deliveryQuery,
  inbox,
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
const deliveryPage = computed(() => Math.floor((deliveryQuery.value.offset || 0) / 20) + 1)
const inboxPage = computed(() => Math.floor((inboxQuery.value.offset || 0) / 20) + 1)
const selectedChannels = computed(() => parseList(form.value.channels))
const usesEmail = computed(() => selectedChannels.value.includes('email'))
const usesWebhook = computed(() => selectedChannels.value.includes('webhook'))
const profilePlatformOptions = computed(() =>
  platformModels.value.map((item) => ({ value: item.platform, label: item.label })),
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
  { label: '规则', value: rules.value.length },
  { label: '已启用', value: rules.value.filter((item) => item.enabled).length },
  { label: '未读', value: unreadCount.value },
  { label: '投递', value: deliveries.value.length },
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
  const platformError = required(profileForm.value.platform, '平台')
  const nameError = required(profileForm.value.profile_name, 'Profile 名称')
  const settings = parseJsonObject(profileForm.value.settings_json, '运行设置 JSON')

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
  const nameError = required(form.value.rule_name, '规则名称')
  const cronError = required(form.value.cron_expr, 'Cron 表达式')
  const channels = parseList(form.value.channels)
  const channelError = channels.length ? '' : '至少需要配置一个渠道。'
  const cooldownError = nonNegativeNumber(form.value.cooldown_minutes, '冷却分钟数')
  const webhookError = usesWebhook.value ? httpUrl(form.value.webhook_url, 'Webhook 地址') : ''
  const smtpPortError = usesEmail.value ? nonNegativeNumber(form.value.smtp_port, 'SMTP 端口') : ''
  const smtpTimeoutError = usesEmail.value ? nonNegativeNumber(form.value.smtp_timeout_seconds, 'SMTP 超时秒数') : ''

  if (nameError) errors.rule_name = nameError
  if (cronError) errors.cron_expr = cronError
  if (channelError) errors.channels = channelError
  if (cooldownError) errors.cooldown_minutes = cooldownError
  if (webhookError) errors.webhook_url = webhookError
  if (usesEmail.value) {
    const recipientsError = required(form.value.email_recipients, '邮件接收人')
    const smtpHostError = required(form.value.smtp_host, 'SMTP 主机')
    const smtpFromError = required(form.value.smtp_from, '发件人')
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
    error.value = '请先修正 Profile 表单错误。'
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
    message.value = '平台登入 Profile 已创建。'
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
  const nextValue = window.prompt('输入新的 credentials_ref。留空则取消。')
  if (!nextValue) return
  message.value = ''
  error.value = ''
  try {
    await updatePlatformProfile(profileId, { credentials_ref: nextValue })
    message.value = '登入凭据已更新。'
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
    title: '删除平台 Profile',
    message: '采集任务将无法继续复用这个登录态。原始凭据不会在页面保留。确认删除吗？',
    confirmLabel: '删除 Profile',
  })
  if (!confirmed) return

  message.value = ''
  error.value = ''
  try {
    await deletePlatformProfile(profileId)
    const { [profileId]: _removed, ...rest } = profileDiagnostics.value
    profileDiagnostics.value = rest
    message.value = '平台登入 Profile 已删除。'
    await fetchProfiles()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function submitRule() {
  message.value = ''
  error.value = ''
  if (!validateRuleForm()) {
    error.value = '请先修正通知规则表单错误。'
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
    message.value = '通知规则已创建。'
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
    message.value = enabled ? '规则已启用。' : '规则已停用。'
    await fetchItems()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function removeRule(ruleId: string) {
  const confirmed = await requestConfirm({
    title: '删除通知规则',
    message: '该规则后续不会再产生 scheduled digest 投递。确认删除吗？',
    confirmLabel: '删除规则',
  })
  if (!confirmed) return

  message.value = ''
  error.value = ''
  try {
    await deleteNotificationRule(ruleId)
    message.value = '规则已删除。'
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
    message.value = '定时摘要已执行评估。'
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

async function moveDeliveryPage(direction: number) {
  const currentOffset = deliveryQuery.value.offset || 0
  const nextOffset = Math.max(0, currentOffset + direction * 20)
  await updateDeliveryQuery({ offset: nextOffset })
}

async function retryDelivery(deliveryId: string) {
  message.value = ''
  error.value = ''
  busy.value = true
  try {
    const delivery = await retryNotificationDelivery(deliveryId)
    message.value = delivery.status === 'sent' ? '投递重试成功。' : '投递已重试，但仍然失败。'
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
    message.value = read ? '通知已标记为已读。' : '通知已标记为未读。'
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
    message.value = `已标记 ${result.updated_count} 条通知为已读。`
    await fetchItems()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function moveInboxPage(direction: number) {
  const currentOffset = inboxQuery.value.offset || 0
  const nextOffset = Math.max(0, currentOffset + direction * 20)
  await updateInboxQuery({ offset: nextOffset })
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
            <h2>平台登入 Profile</h2>
            <p>保存 cookie/state_file 等登录状态，采集任务通过 auth_profile_id 复用。</p>
          </div>
        </div>

        <AppAlert v-if="platformModelsError" tone="error" title="平台模型加载失败" :message="platformModelsError" />
        <PermissionGate area="operations">
        <form class="settings-form" @submit.prevent="submitProfile">
          <div class="grid-two">
            <label class="field">
              <span>平台</span>
              <select v-model="profileForm.platform" :disabled="platformModelsLoading && !profilePlatformOptions.length">
                <option v-for="item in profilePlatformOptions" :key="item.value" :value="item.value">
                  {{ item.label }}
                </option>
              </select>
              <FieldError :message="profileErrors.platform" />
            </label>
            <label class="field">
              <span>认证类型</span>
              <select v-model="profileForm.auth_type">
                <option value="cookie">cookie</option>
                <option value="state_file">state_file</option>
                <option value="qrcode">qrcode</option>
                <option value="phone">phone</option>
              </select>
            </label>
          </div>

          <label class="field">
            <span>Profile 名称</span>
            <input v-model="profileForm.profile_name" required placeholder="例：小红书生产 Cookie" />
            <FieldError :message="profileErrors.profile_name" />
          </label>

          <label class="field">
            <span>credentials_ref</span>
            <textarea v-model="profileForm.credentials_ref" rows="3" placeholder="Cookie 文本或 state_file 路径"></textarea>
          </label>

          <label class="field">
            <span>运行设置 JSON</span>
            <textarea v-model="profileForm.settings_json" rows="4" placeholder='{"headless": true}'></textarea>
            <FieldError :message="profileErrors.settings_json" />
          </label>

          <div class="actions">
            <button class="primary-button" :disabled="busy" type="submit">
              {{ busy ? '保存中...' : '创建 Profile' }}
            </button>
          </div>
        </form>
        </PermissionGate>
      </section>

      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Profile 列表</h2>
            <p>诊断只返回脱敏信息，原始凭据不会显示在页面中。</p>
          </div>
        </div>

        <LoadingState v-if="profilesLoading" title="正在加载平台 Profile..." />
        <AppAlert v-else-if="profilesLoadError" tone="error" title="加载失败" :message="profilesLoadError" />
        <div v-else class="item-list">
          <article v-for="profile in profiles" :key="profile.id" class="list-item">
            <div class="item-main">
              <div>
                <strong>{{ profile.profile_name }}</strong>
                <p>{{ profile.platform }} · {{ profile.auth_type }} · {{ profile.id }}</p>
              </div>
              <span class="status-badge">{{ profile.credentials_ref ? '已配置' : '待配置' }}</span>
            </div>
            <div class="item-meta">
              <span>凭据：{{ profile.credentials_ref || '-' }}</span>
              <span>更新：{{ profile.updated_at }}</span>
            </div>
            <div class="actions">
              <PermissionGate area="operations" compact>
              <button class="secondary-button" type="button" @click="inspectProfile(profile.id)">诊断</button>
              <button class="secondary-button" type="button" @click="rotateProfile(profile.id)">更新凭据</button>
              <button class="secondary-button destructive" type="button" @click="removeProfile(profile.id)">删除</button>
              </PermissionGate>
            </div>
            <pre v-if="profileDiagnostics[profile.id]">{{ JSON.stringify(profileDiagnostics[profile.id], null, 2) }}</pre>
          </article>
          <div v-if="!profiles.length" class="muted">暂无平台登入 Profile。</div>
        </div>
      </section>
    </div>

    <div class="split-grid">
      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>通知规则</h2>
            <p>配置 scheduled digest 规则，按风险、场景、平台和冷却时间过滤。</p>
          </div>
        </div>

        <PermissionGate area="operations">
        <form class="settings-form" @submit.prevent="submitRule">
          <label class="field">
            <span>规则名称</span>
            <input v-model="form.rule_name" required placeholder="例：高风险导流日报" />
            <FieldError :message="ruleErrors.rule_name" />
          </label>

          <div class="grid-two">
            <label class="field">
              <span>风险阈值</span>
              <select v-model="form.risk_level_threshold">
                <option value="low">low</option>
                <option value="medium">medium</option>
                <option value="high">high</option>
                <option value="critical">critical</option>
              </select>
            </label>
            <label class="field">
              <span>Cron 表达式</span>
              <input v-model="form.cron_expr" required placeholder="*/30 * * * *" />
              <FieldError :message="ruleErrors.cron_expr" />
            </label>
          </div>

          <div class="grid-two">
            <label class="field">
              <span>场景</span>
              <input v-model="form.scenario_types" placeholder="lead_diversion,seller_risk" />
            </label>
            <label class="field">
              <span>平台</span>
              <input v-model="form.platforms" placeholder="xhs,dy,xianyu" />
            </label>
          </div>

          <div class="grid-two">
            <label class="field">
              <span>渠道</span>
              <input v-model="form.channels" required placeholder="internal_inbox,email,webhook" />
              <FieldError :message="ruleErrors.channels" />
            </label>
            <label class="field">
              <span>冷却分钟数</span>
              <input v-model.number="form.cooldown_minutes" min="0" step="1" type="number" />
              <FieldError :message="ruleErrors.cooldown_minutes" />
            </label>
          </div>

          <div v-if="usesEmail" class="channel-config">
            <h3>邮件渠道</h3>
            <div class="grid-two">
              <label class="field">
                <span>邮件接收人</span>
                <input v-model="form.email_recipients" placeholder="risk@example.com,ops@example.com" />
                <FieldError :message="ruleErrors.email_recipients" />
              </label>
              <label class="field">
                <span>SMTP 主机</span>
                <input v-model="form.smtp_host" placeholder="smtp.example.com" />
                <FieldError :message="ruleErrors.smtp_host" />
              </label>
            </div>
            <div class="grid-two">
              <label class="field">
                <span>SMTP 端口</span>
                <input v-model.number="form.smtp_port" min="1" step="1" type="number" />
                <FieldError :message="ruleErrors.smtp_port" />
              </label>
              <label class="field">
                <span>发件人</span>
                <input v-model="form.smtp_from" placeholder="platform@example.com" />
                <FieldError :message="ruleErrors.smtp_from" />
              </label>
            </div>
            <div class="grid-two">
              <label class="field">
                <span>SMTP 用户名</span>
                <input v-model="form.smtp_username" placeholder="可选" />
              </label>
              <label class="field">
                <span>SMTP 密码</span>
                <input v-model="form.smtp_password" autocomplete="new-password" placeholder="可选" type="password" />
              </label>
            </div>
            <div class="grid-two">
              <label class="field">
                <span>SMTP 超时秒数</span>
                <input v-model.number="form.smtp_timeout_seconds" min="1" step="1" type="number" />
                <FieldError :message="ruleErrors.smtp_timeout_seconds" />
              </label>
              <label class="toggle-line channel-toggle">
                <input v-model="form.smtp_use_tls" type="checkbox" />
                <span>启用 STARTTLS</span>
              </label>
            </div>
          </div>

          <div v-if="usesWebhook" class="channel-config">
            <h3>Webhook 渠道</h3>
            <label class="field">
              <span>Webhook 地址</span>
              <input v-model="form.webhook_url" placeholder="https://example.test/webhook" />
              <FieldError :message="ruleErrors.webhook_url" />
            </label>
          </div>

          <label class="toggle-line">
            <input v-model="form.enabled" type="checkbox" />
            <span>启用</span>
          </label>

          <div class="actions">
            <button class="primary-button" :disabled="busy" type="submit">
              {{ busy ? '保存中...' : '创建规则' }}
            </button>
            <button class="secondary-button" :disabled="busy" type="button" @click="runNow">
              立即执行定时任务
            </button>
          </div>
        </form>
        </PermissionGate>
      </section>

      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>规则列表</h2>
            <p>禁用规则不会被 cron 执行；last run 只在投递记录落库后更新。</p>
          </div>
        </div>

        <LoadingState v-if="isLoading" title="正在加载通知设置..." />
        <AppAlert v-else-if="loadError" tone="error" title="加载失败" :message="loadError" />
        <div v-else class="item-list">
          <article v-for="item in rules" :key="item.id" class="list-item">
            <div class="item-main">
              <div>
                <strong>{{ item.rule_name }}</strong>
                <p>{{ item.event_type }} · {{ item.cron_expr }} · {{ item.risk_level_threshold }}</p>
              </div>
              <span class="status-badge" :class="{ disabled: !item.enabled }">
                {{ item.enabled ? '已启用' : '已停用' }}
              </span>
            </div>
            <div class="item-meta">
              <span>渠道：{{ item.channels.join(', ') }}</span>
              <span>最近执行：{{ item.last_executed_at || '-' }}</span>
            </div>
            <div class="actions">
              <PermissionGate area="operations" compact>
              <button class="secondary-button" type="button" @click="toggleRule(item.id, !item.enabled)">
                {{ item.enabled ? '停用' : '启用' }}
              </button>
              <button class="secondary-button destructive" type="button" @click="removeRule(item.id)">删除</button>
              </PermissionGate>
            </div>
          </article>
          <div v-if="!rules.length" class="muted">暂无通知规则。</div>
        </div>
      </section>
    </div>

    <AppAlert v-if="message" tone="success" title="操作成功" :message="message" />
    <AppAlert v-if="error" tone="error" title="操作失败" :message="error" />

    <section class="surface section-card">
      <div class="section-head section-head-inline">
        <div>
          <h2>站内通知中心</h2>
          <p>internal_inbox 投递会进入这里，可作为平台内的待办收件箱。</p>
        </div>
        <PermissionGate area="workflow" compact>
          <button class="secondary-button" type="button" @click="markAllRead">全部已读</button>
        </PermissionGate>
      </div>

      <form class="filter-bar inbox-filter" @submit.prevent="applyInboxFilters">
        <input v-model="inboxFilters.q" placeholder="搜索标题、目标、规则或摘要" />
        <label class="toggle-line">
          <input v-model="inboxFilters.unread_only" type="checkbox" />
          <span>只看未读</span>
        </label>
        <button class="secondary-button" :disabled="busy" type="submit">筛选</button>
      </form>

      <LoadingState v-if="isLoading" title="正在加载站内通知..." />
      <div v-else class="inbox-list">
        <article v-for="item in inbox" :key="item.id" class="inbox-item" :class="{ unread: !item.read }">
          <div class="item-main">
            <div>
              <strong>{{ item.title }}</strong>
              <p>{{ item.rule_name || item.rule_id }} · {{ item.target_type }} · {{ item.created_at }}</p>
            </div>
            <span class="status-badge" :class="{ skipped: item.read }">{{ item.read ? '已读' : '未读' }}</span>
          </div>
          <div class="item-meta">
            <span>{{ item.summary || '暂无摘要' }}</span>
            <span>事件数：{{ item.event_count }} · 目标：{{ item.target_id }}</span>
          </div>
          <div class="actions">
            <PermissionGate area="workflow" compact>
            <button class="secondary-button" type="button" @click="toggleInboxRead(item.id, !item.read)">
              {{ item.read ? '标记未读' : '标记已读' }}
            </button>
            </PermissionGate>
          </div>
        </article>
        <div v-if="!inbox.length" class="muted">暂无站内通知。</div>
      </div>

      <div class="pager">
        <button class="secondary-button" :disabled="(inboxQuery.offset || 0) === 0" type="button" @click="moveInboxPage(-1)">
          上一页
        </button>
        <span>第 {{ inboxPage }} 页</span>
        <button class="secondary-button" :disabled="inbox.length < 20" type="button" @click="moveInboxPage(1)">
          下一页
        </button>
      </div>
    </section>

    <div class="split-grid">
      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>投递记录</h2>
            <p>可按状态、通道、目标类型和关键词追踪最近的投递结果。</p>
          </div>
        </div>

        <form class="filter-bar" @submit.prevent="applyDeliveryFilters">
          <input v-model="deliveryFilters.q" placeholder="搜索投递、目标或错误" />
          <select v-model="deliveryFilters.status">
            <option value="">全部状态</option>
            <option value="sent">已发送</option>
            <option value="failed">失败</option>
            <option value="skipped">已跳过</option>
          </select>
          <select v-model="deliveryFilters.channel">
            <option value="">全部渠道</option>
            <option value="internal_inbox">internal_inbox</option>
            <option value="email">email</option>
            <option value="webhook">webhook</option>
          </select>
          <select v-model="deliveryFilters.target_type">
            <option value="">全部目标</option>
            <option value="signal">signal</option>
            <option value="case">case</option>
            <option value="evidence_packet">evidence_packet</option>
            <option value="scheduled_digest">scheduled_digest</option>
          </select>
          <button class="secondary-button" :disabled="busy" type="submit">筛选</button>
          <button class="secondary-button" :disabled="busy" type="button" @click="resetDeliveryFilters">重置</button>
        </form>

        <div class="item-list">
          <article v-for="item in deliveries" :key="item.id" class="list-item">
            <div class="item-main">
              <div>
                <strong>{{ item.target_type }} · {{ item.target_id }}</strong>
                <p>{{ item.channel }} · {{ item.created_at }}</p>
              </div>
              <span class="status-badge" :class="item.status">{{ item.status }}</span>
            </div>
            <div v-if="item.error_message" class="error-text">{{ item.error_message }}</div>
            <div class="item-meta">
              <span>重试次数：{{ item.retry_count }}</span>
              <span>最近尝试：{{ item.last_attempt_at || '-' }}</span>
            </div>
            <div v-if="item.status === 'failed'" class="actions">
              <PermissionGate area="operations" compact>
              <button class="secondary-button" :disabled="busy" type="button" @click="retryDelivery(item.id)">重试投递</button>
              </PermissionGate>
            </div>
          </article>
          <div v-if="!deliveries.length" class="muted">暂无投递记录。</div>
        </div>

        <div class="pager">
          <button class="secondary-button" :disabled="(deliveryQuery.offset || 0) === 0" type="button" @click="moveDeliveryPage(-1)">
            上一页
          </button>
          <span>第 {{ deliveryPage }} 页</span>
          <button class="secondary-button" :disabled="deliveries.length < 20" type="button" @click="moveDeliveryPage(1)">
            下一页
          </button>
        </div>
      </section>

      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>最近运行</h2>
            <p>手动运行 scheduled digest 的结果摘要。</p>
          </div>
        </div>
        <pre v-if="runResult">{{ JSON.stringify(runResult, null, 2) }}</pre>
        <div v-else class="muted">暂无运行结果。</div>
      </section>
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

.pager {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 16px;
  color: #475569;
  font-weight: 700;
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
