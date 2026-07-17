<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchHealth } from '../../api/health'
import { useAuth } from '../../composables/useAuth'
import { getLocalizedRouteTitle, useI18n } from '../../composables/useI18n'
import { useTheme } from '../../composables/useTheme'
import type { Locale } from '../../i18n/messages'
import { roleLabel } from '../../lib/permissions'
import AppSelect from '../ui/AppSelect.vue'

type BackendStatus = 'checking' | 'ready' | 'offline'

const route = useRoute()
const router = useRouter()
const { signOut, user } = useAuth()
const { locale, localeOptions, setLocale, t } = useI18n()
const { theme, themeOptions, setTheme } = useTheme()
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

function changeLocale(nextLocale: string | number) {
  setLocale(nextLocale as Locale)
  document.title = getLocalizedRouteTitle(route.meta.titleKey as string | undefined)
}
</script>

<template>
  <header class="header glass">
    <div class="header-brand">
      <div class="brand-mark">
        <img
          :src="theme === 'pink' ? '/brand/logo-pink.png' : '/brand/logo-blue.png'"
          alt="Digital Forensics"
        />
      </div>
      <div>
        <strong>{{ t('app.name') }}</strong>
        <span>{{ t('app.subtitle') }}</span>
      </div>
    </div>
    <div class="header-actions">
      <div class="theme-toggle" role="group" aria-label="theme">
        <button
          v-for="option in themeOptions"
          :key="option.value"
          type="button"
          class="theme-chip"
          :class="[option.value, { active: theme === option.value }]"
          :title="option.label"
          @click="setTheme(option.value)"
        >
          <span class="theme-swatch" />
          {{ option.label }}
        </button>
      </div>
      <label class="locale-control">
        <span>{{ t('header.language') }}</span>
        <AppSelect
          class="locale-select"
          size="sm"
          :model-value="locale"
          :options="localeOptions"
          :aria-label="t('header.language')"
          @update:model-value="changeLocale"
        />
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
  padding: 0 22px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid color-mix(in oklch, var(--primary) 12%, var(--border));
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.7) inset, 0 8px 24px -20px var(--brand-glow);
}

.header-brand {
  display: flex;
  align-items: center;
  gap: 14px;
}

.brand-mark {
  width: 46px;
  height: 46px;
  display: grid;
  place-items: center;
  background: transparent;
  border: 0;
  padding: 0;
  filter: drop-shadow(0 6px 12px color-mix(in oklch, var(--primary) 28%, transparent));
}

.brand-mark img {
  width: 100%;
  height: 100%;
  object-fit: contain;
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

.theme-toggle {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 3px;
  border-radius: 999px;
  border: 1px solid color-mix(in oklch, var(--primary) 16%, var(--border));
  background: rgba(255, 255, 255, 0.7);
}

.theme-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 11px 5px 8px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--muted-foreground);
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
}

.theme-swatch {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.06) inset;
}

.theme-chip.blue .theme-swatch {
  background: linear-gradient(135deg, #1e40e6, #6d8bff);
}

.theme-chip.pink .theme-swatch {
  background: linear-gradient(135deg, #db2f8e, #f473b6);
}

.theme-chip.active {
  color: #fff;
  background: var(--primary);
  box-shadow: 0 6px 14px -6px var(--brand-glow);
}

.theme-chip.active .theme-swatch {
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.7) inset;
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
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.locale-select {
  width: auto;
  min-width: 104px;
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
