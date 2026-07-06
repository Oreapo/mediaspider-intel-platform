<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { useAuth } from '../../composables/useAuth'
import { useI18n } from '../../composables/useI18n'
import { hasRole, type AppRole } from '../../lib/permissions'
import AppIcon from '../ui/AppIcon.vue'

const route = useRoute()
const { user } = useAuth()
const { t } = useI18n()

type SidebarNavItem = { to: string; labelKey: string; icon: string; roles?: AppRole[] }
type SecondaryNavItem = SidebarNavItem & { hintKey?: string }

// Primary navigation follows the analyst workflow stages, not the object model.
// Datasets / analysis / evidence / reports are intentionally demoted to the
// contextual secondary panel below (source tracing and deliverables).
const primaryNavItems = [
  { to: '/dashboard', labelKey: 'nav.dashboard', icon: 'shield' },
  { to: '/tasks', labelKey: 'nav.tasks', icon: 'activity', roles: ['admin', 'operator', 'analyst'] },
  { to: '/signals', labelKey: 'nav.signals', icon: 'search' },
  { to: '/entities', labelKey: 'nav.entities', icon: 'users' },
  { to: '/cases', labelKey: 'nav.cases', icon: 'briefcase' },
] satisfies SidebarNavItem[]

const systemNavItems = [
  { to: '/logs', labelKey: 'nav.logs', icon: 'list', roles: ['admin', 'operator', 'analyst'] },
  { to: '/settings', labelKey: 'nav.settings', icon: 'sliders', roles: ['admin', 'operator'] },
  { to: '/help', labelKey: 'nav.help', icon: 'help' },
] satisfies SidebarNavItem[]

const secondaryGroups: Record<string, { titleKey: string; items: SecondaryNavItem[] }> = {
  '/dashboard': {
    titleKey: 'sidebar.dashboardActions',
    items: [
      { to: '/tasks', labelKey: 'dashboard.quickCreateTask', hintKey: 'dashboard.quickCreateTaskHint', icon: 'activity', roles: ['admin', 'operator', 'analyst'] },
      { to: '/signals', labelKey: 'dashboard.quickReviewSignals', hintKey: 'dashboard.quickReviewSignalsHint', icon: 'search' },
      { to: '/cases', labelKey: 'dashboard.quickAdvanceCases', hintKey: 'dashboard.quickAdvanceCasesHint', icon: 'briefcase' },
      { to: '/reports', labelKey: 'dashboard.quickGenerateReports', hintKey: 'dashboard.quickGenerateReportsHint', icon: 'file' },
    ],
  },
  '/tasks': {
    titleKey: 'sidebar.relatedActions',
    items: [
      { to: '/datasets', labelKey: 'nav.datasets', hintKey: 'datasets.listDescription', icon: 'layers' },
      { to: '/logs', labelKey: 'nav.logs', hintKey: 'logs.description', icon: 'list', roles: ['admin', 'operator', 'analyst'] },
      { to: '/settings', labelKey: 'nav.settings', hintKey: 'sidebar.settingsHint', icon: 'sliders', roles: ['admin', 'operator'] },
    ],
  },
  '/datasets': {
    titleKey: 'sidebar.relatedActions',
    items: [
      { to: '/signals', labelKey: 'nav.signals', hintKey: 'signals.queueDescription', icon: 'search' },
      { to: '/analysis', labelKey: 'nav.analysis', hintKey: 'sidebar.analysisHint', icon: 'chart' },
      { to: '/cases', labelKey: 'nav.cases', hintKey: 'cases.listDescription', icon: 'briefcase' },
    ],
  },
  '/signals': {
    titleKey: 'sidebar.relatedActions',
    items: [
      { to: '/datasets', labelKey: 'nav.datasets', hintKey: 'datasets.listDescription', icon: 'layers' },
      { to: '/analysis', labelKey: 'nav.analysis', hintKey: 'sidebar.analysisHint', icon: 'chart' },
      { to: '/entities', labelKey: 'nav.entities', hintKey: 'entities.listDescription', icon: 'users' },
      { to: '/cases', labelKey: 'nav.cases', hintKey: 'cases.listDescription', icon: 'briefcase' },
    ],
  },
  '/entities': {
    titleKey: 'sidebar.relatedActions',
    items: [
      { to: '/signals', labelKey: 'nav.signals', hintKey: 'signals.queueDescription', icon: 'search' },
      { to: '/cases', labelKey: 'nav.cases', hintKey: 'cases.listDescription', icon: 'briefcase' },
      { to: '/analysis', labelKey: 'nav.analysis', hintKey: 'sidebar.analysisHint', icon: 'chart' },
    ],
  },
  '/cases': {
    titleKey: 'sidebar.relatedActions',
    items: [
      { to: '/evidence', labelKey: 'nav.evidence', hintKey: 'evidence.listDescription', icon: 'package' },
      { to: '/reports', labelKey: 'nav.reports', hintKey: 'reports.listDescription', icon: 'file' },
      { to: '/signals', labelKey: 'nav.signals', hintKey: 'signals.queueDescription', icon: 'search' },
    ],
  },
  '/evidence': {
    titleKey: 'sidebar.relatedActions',
    items: [
      { to: '/cases', labelKey: 'nav.cases', hintKey: 'cases.listDescription', icon: 'briefcase' },
      { to: '/reports', labelKey: 'nav.reports', hintKey: 'reports.listDescription', icon: 'file' },
    ],
  },
  '/analysis': {
    titleKey: 'sidebar.relatedActions',
    items: [
      { to: '/datasets', labelKey: 'nav.datasets', hintKey: 'datasets.listDescription', icon: 'layers' },
      { to: '/signals', labelKey: 'nav.signals', hintKey: 'signals.queueDescription', icon: 'search' },
      { to: '/reports', labelKey: 'nav.reports', hintKey: 'reports.listDescription', icon: 'file' },
    ],
  },
  '/reports': {
    titleKey: 'sidebar.relatedActions',
    items: [
      { to: '/cases', labelKey: 'nav.cases', hintKey: 'cases.listDescription', icon: 'briefcase' },
      { to: '/evidence', labelKey: 'nav.evidence', hintKey: 'evidence.listDescription', icon: 'package' },
    ],
  },
  '/logs': {
    titleKey: 'sidebar.relatedActions',
    items: [
      { to: '/tasks', labelKey: 'nav.tasks', hintKey: 'tasks.listDescription', icon: 'activity', roles: ['admin', 'operator', 'analyst'] },
      { to: '/settings', labelKey: 'nav.settings', hintKey: 'sidebar.settingsHint', icon: 'sliders', roles: ['admin', 'operator'] },
    ],
  },
  '/settings': {
    titleKey: 'sidebar.relatedActions',
    items: [
      { to: '/tasks', labelKey: 'nav.tasks', hintKey: 'tasks.listDescription', icon: 'activity', roles: ['admin', 'operator', 'analyst'] },
      { to: '/logs', labelKey: 'nav.logs', hintKey: 'logs.description', icon: 'list', roles: ['admin', 'operator', 'analyst'] },
    ],
  },
  '/help': {
    titleKey: 'sidebar.relatedActions',
    items: [
      { to: '/dashboard', labelKey: 'nav.dashboard', hintKey: 'dashboard.heroDescription', icon: 'shield' },
      { to: '/tasks', labelKey: 'nav.tasks', hintKey: 'tasks.listDescription', icon: 'activity', roles: ['admin', 'operator', 'analyst'] },
      { to: '/cases', labelKey: 'nav.cases', hintKey: 'cases.listDescription', icon: 'briefcase' },
    ],
  },
}

const visiblePrimaryNavItems = computed(() =>
  primaryNavItems.filter((item) => !item.roles || hasRole(user.value, item.roles)),
)
const visibleSystemNavItems = computed(() =>
  systemNavItems.filter((item) => !item.roles || hasRole(user.value, item.roles)),
)

const routeRoot = computed(() => `/${route.path.split('/')[1] || 'dashboard'}`)
const activeSecondaryGroup = computed(() => secondaryGroups[routeRoot.value] ?? secondaryGroups['/dashboard'])
const visibleSecondaryItems = computed(() =>
  activeSecondaryGroup.value.items.filter((item) => !item.roles || hasRole(user.value, item.roles)),
)
</script>

<template>
  <div class="sidebar-stack">
    <section v-if="visibleSecondaryItems.length" class="side-actions surface-subtle">
      <div class="side-actions-head">
        <small>{{ t(activeSecondaryGroup.titleKey) }}</small>
      </div>
      <RouterLink
        v-for="item in visibleSecondaryItems"
        :key="`${routeRoot}-${item.to}-${item.labelKey}`"
        :to="item.to"
        class="side-action"
      >
        <span class="side-action-icon"><AppIcon :name="item.icon" :size="15" /></span>
        <span>
          <strong>{{ t(item.labelKey) }}</strong>
          <small v-if="item.hintKey">{{ t(item.hintKey) }}</small>
        </span>
      </RouterLink>
    </section>

    <nav class="sidebar-nav">
      <RouterLink
        v-for="item in visiblePrimaryNavItems"
        :key="item.to"
        :to="item.to"
        class="nav-btn"
        :class="{ active: route.path === item.to || (item.to !== '/dashboard' && route.path.startsWith(`${item.to}/`)) }"
      >
        <span class="nav-icon"><AppIcon :name="item.icon" :size="16" /></span>
        <span>{{ t(item.labelKey) }}</span>
      </RouterLink>

      <div v-if="visibleSystemNavItems.length" class="nav-divider">
        <small>{{ t('sidebar.systemSection') }}</small>
      </div>

      <RouterLink
        v-for="item in visibleSystemNavItems"
        :key="item.to"
        :to="item.to"
        class="nav-btn"
        :class="{ active: route.path === item.to || route.path.startsWith(`${item.to}/`) }"
      >
        <span class="nav-icon"><AppIcon :name="item.icon" :size="16" /></span>
        <span>{{ t(item.labelKey) }}</span>
      </RouterLink>
    </nav>
  </div>
</template>

<style scoped>
.sidebar-stack {
  display: grid;
  gap: 16px;
}

.sidebar-nav {
  display: grid;
  gap: 4px;
}

.nav-divider {
  display: flex;
  align-items: center;
  padding: 12px 12px 4px;
}

.nav-divider small {
  color: #94a3b8;
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.nav-btn {
  position: relative;
  width: 100%;
  height: 46px;
  border-radius: var(--radius);
  border: 1px solid transparent;
  background: transparent;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 12px;
  color: #475569;
  font-weight: 700;
  transition: background 180ms ease, color 180ms ease, border-color 180ms ease, transform 150ms ease;
}

.nav-btn:hover {
  background: rgba(255, 255, 255, 0.82);
  color: #0f172a;
  transform: translateX(2px);
}

.nav-btn.active {
  background: linear-gradient(90deg, color-mix(in oklch, var(--primary) 14%, transparent), rgba(15, 118, 110, 0.055));
  color: #0f172a;
  border-color: color-mix(in oklch, var(--primary) 18%, transparent);
}

.nav-btn.active::before {
  content: "";
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 24px;
  border-radius: 0 999px 999px 0;
  background: linear-gradient(180deg, var(--primary), var(--primary-strong));
}

.nav-icon {
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  border-radius: var(--radius);
  border: 1px solid rgba(190, 202, 216, 0.58);
  background: rgba(255, 255, 255, 0.82);
  font-size: 11px;
  font-weight: 800;
}

.nav-btn.active .nav-icon {
  border-color: color-mix(in oklch, var(--primary) 24%, transparent);
  background: rgba(240, 253, 250, 0.92);
  color: var(--primary);
}

.side-actions {
  display: grid;
  gap: 8px;
  padding: 12px;
  border-radius: var(--radius);
}

.side-actions-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.side-actions-head small {
  color: #64748b;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.side-action {
  display: grid;
  grid-template-columns: 26px minmax(0, 1fr);
  gap: 9px;
  align-items: start;
  padding: 10px;
  border: 1px solid rgba(215, 224, 234, 0.72);
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.72);
  transition: transform 150ms ease, border-color 180ms ease, background 180ms ease;
}

.side-action:hover {
  transform: translateX(2px);
  border-color: color-mix(in oklch, var(--primary) 18%, transparent);
  background: rgba(255, 255, 255, 0.92);
}

.side-action-icon {
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  border-radius: var(--radius);
  background: rgba(240, 253, 250, 0.92);
  color: var(--primary);
  font-size: 11px;
  font-weight: 900;
}

.side-action strong,
.side-action small {
  display: block;
  min-width: 0;
  overflow-wrap: anywhere;
}

.side-action strong {
  color: #0f172a;
  font-size: 13px;
}

.side-action small {
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.45;
}
</style>
