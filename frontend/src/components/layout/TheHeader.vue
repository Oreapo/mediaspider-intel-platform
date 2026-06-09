<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchHealth } from '../../api/health'
import { useAuth } from '../../composables/useAuth'
import { getLocalizedRouteTitle, useI18n } from '../../composables/useI18n'
import type { Locale } from '../../i18n/messages'
import { roleLabel } from '../../lib/permissions'

type BackendStatus = 'checking' | 'ready' | 'offline'

const route = useRoute()
const router = useRouter()
const { signOut, user } = useAuth()
const { locale, localeOptions, setLocale, t } = useI18n()
const backendStatus = ref<BackendStatus>('checking')
let backendHealthTimer: number | undefined

const backendStatusLabel = computed(() => {
  if (backendStatus.value === 'ready') return t('header.backendReady')
  if (backendStatus.value === 'offline') return t('header.backendUnavailable')
  return t('header.backendChecking')
})

async function refreshBackendStatus() {
  try {
    const health = await fetchHealth()
    backendStatus.value = health.status === 'ok' ? 'ready' : 'offline'
  } catch {
    backendStatus.value = 'offline'
  }
}

onMounted(() => {
  void refreshBackendStatus()
  backendHealthTimer = window.setInterval(() => {
    void refreshBackendStatus()
  }, 30000)
})

onBeforeUnmount(() => {
  if (backendHealthTimer !== undefined) {
    window.clearInterval(backendHealthTimer)
  }
})

async function logout() {
  await signOut()
  await router.replace('/login')
}

function changeLocale(event: Event) {
  const nextLocale = (event.target as HTMLSelectElement).value as Locale
  setLocale(nextLocale)
  document.title = getLocalizedRouteTitle(route.meta.titleKey as string | undefined)
}
</script>

<template>
  <header class="header glass">
    <div class="header-brand">
      <div class="brand-mark">MS</div>
      <div>
        <strong>{{ t('app.name') }}</strong>
        <span>{{ t('app.subtitle') }}</span>
      </div>
    </div>
    <div class="header-actions">
      <label class="locale-control">
        <span>{{ t('header.language') }}</span>
        <select :value="locale" @change="changeLocale">
          <option v-for="option in localeOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </label>
      <div class="header-code">{{ t('header.opsCode') }}</div>
      <div v-if="user" class="user-pill">
        <strong>{{ user.display_name }}</strong>
        <span>{{ roleLabel(user.role) }}</span>
      </div>
      <div class="status-pill" :class="backendStatus" :title="backendStatusLabel">
        <span class="status-dot"></span>
        <span>{{ backendStatusLabel }}</span>
      </div>
      <button class="logout-button" type="button" @click="logout">{{ t('header.logout') }}</button>
    </div>
  </header>
</template>

<style scoped>
.header {
  position: sticky;
  top: 0;
  z-index: 50;
  height: 64px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid rgba(215, 224, 234, 0.74);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.7) inset;
}

.header-brand {
  display: flex;
  align-items: center;
  gap: 14px;
}

.brand-mark {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border-radius: var(--radius);
  background:
    linear-gradient(135deg, color-mix(in oklch, var(--primary) 70%, black), var(--accent)),
    linear-gradient(90deg, rgba(255, 255, 255, 0.18) 1px, transparent 1px);
  color: #fff;
  font-size: 14px;
  font-weight: 800;
  box-shadow: 0 10px 22px rgba(21, 94, 117, 0.24);
}

.header-brand strong {
  display: block;
  font-size: 17px;
  letter-spacing: 0;
}

.header-brand span {
  color: #64748b;
  font-size: 13px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-code {
  padding: 7px 10px;
  border: 1px solid rgba(190, 202, 216, 0.72);
  border-radius: var(--radius);
  color: #475569;
  background: rgba(248, 250, 252, 0.72);
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
}

.locale-control {
  min-height: 34px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border: 1px solid rgba(190, 202, 216, 0.72);
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.76);
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.locale-control select {
  border: 0;
  background: transparent;
  color: #0f172a;
  font: inherit;
  outline: none;
  cursor: pointer;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 7px 11px;
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.74);
  border: 1px solid rgba(226, 232, 240, 0.9);
  font-size: 13px;
  font-weight: 700;
}

.user-pill {
  display: grid;
  gap: 2px;
  padding: 6px 10px;
  border: 1px solid rgba(190, 202, 216, 0.72);
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.74);
}

.user-pill strong {
  font-size: 13px;
  line-height: 1;
}

.user-pill span {
  color: #64748b;
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
}

.logout-button {
  min-height: 34px;
  border: 1px solid rgba(190, 202, 216, 0.72);
  border-radius: var(--radius);
  background: rgba(248, 250, 252, 0.86);
  color: #334155;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
}

.status-dot {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: #10b981;
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.12);
}

.status-pill.ready .status-dot {
  background: var(--success);
  box-shadow: 0 0 0 3px color-mix(in oklch, var(--success) 20%, transparent);
}

.status-pill.checking .status-dot {
  background: var(--warning);
  box-shadow: 0 0 0 3px color-mix(in oklch, var(--warning) 20%, transparent);
}

.status-pill.offline .status-dot {
  background: var(--destructive);
  box-shadow: 0 0 0 3px color-mix(in oklch, var(--destructive) 20%, transparent);
}

@media (max-width: 780px) {
  .header {
    height: auto;
    min-height: 64px;
    align-items: flex-start;
    padding: 12px 14px;
  }

  .header-actions {
    justify-content: flex-end;
    flex-wrap: wrap;
  }
}
</style>
