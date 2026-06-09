<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { useAuth } from '../../composables/useAuth'
import { useI18n } from '../../composables/useI18n'
import { hasRole, type AppRole } from '../../lib/permissions'

const route = useRoute()
const { user } = useAuth()
const { t } = useI18n()

type SidebarNavItem = { to: string; labelKey: string; icon: string; roles?: AppRole[] }
type SecondaryNavItem = SidebarNavItem & { hintKey?: string }

const navItems = [
  { to: '/dashboard', labelKey: 'nav.dashboard', icon: '首' },
  { to: '/tasks', labelKey: 'nav.tasks', icon: '采', roles: ['admin', 'operator', 'analyst'] },
  { to: '/datasets', labelKey: 'nav.datasets', icon: '数' },
  { to: '/signals', labelKey: 'nav.signals', icon: '信' },
  { to: '/entities', labelKey: 'nav.entities', icon: '实' },
  { to: '/cases', labelKey: 'nav.cases', icon: '案' },
  { to: '/evidence', labelKey: 'nav.evidence', icon: '证' },
  { to: '/analysis', labelKey: 'nav.analysis', icon: '析' },
  { to: '/reports', labelKey: 'nav.reports', icon: '报' },
  { to: '/logs', labelKey: 'nav.logs', icon: '志', roles: ['admin', 'operator', 'analyst'] },
  { to: '/settings', labelKey: 'nav.settings', icon: '设', roles: ['admin', 'operator'] },
  { to: '/help', labelKey: 'nav.help', icon: '帮' },
] satisfies SidebarNavItem[]

const secondaryGroups: Record<string, { titleKey: string; items: SecondaryNavItem[] }> = {
  '/dashboard': {
    titleKey: 'sidebar.dashboardActions',
    items: [
      { to: '/tasks', labelKey: 'dashboard.quickCreateTask', hintKey: 'dashboard.quickCreateTaskHint', icon: '采', roles: ['admin', 'operator', 'analyst'] },
      { to: '/signals', labelKey: 'dashboard.quickReviewSignals', hintKey: 'dashboard.quickReviewSignalsHint', icon: '信' },
      { to: '/cases', labelKey: 'dashboard.quickAdvanceCases', hintKey: 'dashboard.quickAdvanceCasesHint', icon: '案' },
      { to: '/reports', labelKey: 'dashboard.quickGenerateReports', hintKey: 'dashboard.quickGenerateReportsHint', icon: '报' },
    ],
  },
  '/tasks': {
    titleKey: 'sidebar.relatedActions',
    items: [
      { to: '/datasets', labelKey: 'nav.datasets', hintKey: 'datasets.listDescription', icon: '数' },
      { to: '/logs', labelKey: 'nav.logs', hintKey: 'logs.description', icon: '志', roles: ['admin', 'operator', 'analyst'] },
      { to: '/settings', labelKey: 'nav.settings', hintKey: 'sidebar.settingsHint', icon: '设', roles: ['admin', 'operator'] },
    ],
  },
  '/datasets': {
    titleKey: 'sidebar.relatedActions',
    items: [
      { to: '/signals', labelKey: 'nav.signals', hintKey: 'signals.queueDescription', icon: '信' },
      { to: '/analysis', labelKey: 'nav.analysis', hintKey: 'sidebar.analysisHint', icon: '析' },
      { to: '/cases', labelKey: 'nav.cases', hintKey: 'cases.listDescription', icon: '案' },
    ],
  },
  '/signals': {
    titleKey: 'sidebar.relatedActions',
    items: [
      { to: '/entities', labelKey: 'nav.entities', hintKey: 'entities.listDescription', icon: '实' },
      { to: '/cases', labelKey: 'nav.cases', hintKey: 'cases.listDescription', icon: '案' },
      { to: '/datasets', labelKey: 'nav.datasets', hintKey: 'datasets.listDescription', icon: '数' },
    ],
  },
  '/entities': {
    titleKey: 'sidebar.relatedActions',
    items: [
      { to: '/signals', labelKey: 'nav.signals', hintKey: 'signals.queueDescription', icon: '信' },
      { to: '/cases', labelKey: 'nav.cases', hintKey: 'cases.listDescription', icon: '案' },
      { to: '/analysis', labelKey: 'nav.analysis', hintKey: 'sidebar.analysisHint', icon: '析' },
    ],
  },
  '/cases': {
    titleKey: 'sidebar.relatedActions',
    items: [
      { to: '/evidence', labelKey: 'nav.evidence', hintKey: 'evidence.listDescription', icon: '证' },
      { to: '/reports', labelKey: 'nav.reports', hintKey: 'reports.listDescription', icon: '报' },
      { to: '/signals', labelKey: 'nav.signals', hintKey: 'signals.queueDescription', icon: '信' },
    ],
  },
  '/evidence': {
    titleKey: 'sidebar.relatedActions',
    items: [
      { to: '/cases', labelKey: 'nav.cases', hintKey: 'cases.listDescription', icon: '案' },
      { to: '/reports', labelKey: 'nav.reports', hintKey: 'reports.listDescription', icon: '报' },
    ],
  },
  '/analysis': {
    titleKey: 'sidebar.relatedActions',
    items: [
      { to: '/datasets', labelKey: 'nav.datasets', hintKey: 'datasets.listDescription', icon: '数' },
      { to: '/signals', labelKey: 'nav.signals', hintKey: 'signals.queueDescription', icon: '信' },
      { to: '/reports', labelKey: 'nav.reports', hintKey: 'reports.listDescription', icon: '报' },
    ],
  },
  '/reports': {
    titleKey: 'sidebar.relatedActions',
    items: [
      { to: '/cases', labelKey: 'nav.cases', hintKey: 'cases.listDescription', icon: '案' },
      { to: '/evidence', labelKey: 'nav.evidence', hintKey: 'evidence.listDescription', icon: '证' },
    ],
  },
  '/logs': {
    titleKey: 'sidebar.relatedActions',
    items: [
      { to: '/tasks', labelKey: 'nav.tasks', hintKey: 'tasks.listDescription', icon: '采', roles: ['admin', 'operator', 'analyst'] },
      { to: '/settings', labelKey: 'nav.settings', hintKey: 'sidebar.settingsHint', icon: '设', roles: ['admin', 'operator'] },
    ],
  },
  '/settings': {
    titleKey: 'sidebar.relatedActions',
    items: [
      { to: '/tasks', labelKey: 'nav.tasks', hintKey: 'tasks.listDescription', icon: '采', roles: ['admin', 'operator', 'analyst'] },
      { to: '/logs', labelKey: 'nav.logs', hintKey: 'logs.description', icon: '志', roles: ['admin', 'operator', 'analyst'] },
    ],
  },
  '/help': {
    titleKey: 'sidebar.relatedActions',
    items: [
      { to: '/dashboard', labelKey: 'nav.dashboard', hintKey: 'dashboard.heroDescription', icon: '首' },
      { to: '/tasks', labelKey: 'nav.tasks', hintKey: 'tasks.listDescription', icon: '采', roles: ['admin', 'operator', 'analyst'] },
      { to: '/cases', labelKey: 'nav.cases', hintKey: 'cases.listDescription', icon: '案' },
    ],
  },
}

const visibleNavItems = computed(() =>
  navItems.filter((item) => !item.roles || hasRole(user.value, item.roles)),
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
        <span class="side-action-icon">{{ item.icon }}</span>
        <span>
          <strong>{{ t(item.labelKey) }}</strong>
          <small v-if="item.hintKey">{{ t(item.hintKey) }}</small>
        </span>
      </RouterLink>
    </section>

    <nav class="sidebar-nav">
      <RouterLink
        v-for="item in visibleNavItems"
        :key="item.to"
        :to="item.to"
        class="nav-btn"
        :class="{ active: route.path === item.to || (item.to !== '/dashboard' && route.path.startsWith(`${item.to}/`)) }"
      >
        <span class="nav-icon">{{ item.icon }}</span>
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
  background: linear-gradient(90deg, rgba(21, 94, 117, 0.14), rgba(15, 118, 110, 0.055));
  color: #0f172a;
  border-color: rgba(21, 94, 117, 0.18);
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
  background: linear-gradient(180deg, var(--primary), var(--accent));
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
  border-color: rgba(21, 94, 117, 0.24);
  background: rgba(240, 253, 250, 0.92);
  color: #0f766e;
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
  border-color: rgba(21, 94, 117, 0.18);
  background: rgba(255, 255, 255, 0.92);
}

.side-action-icon {
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  border-radius: var(--radius);
  background: rgba(240, 253, 250, 0.92);
  color: #0f766e;
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
