import { createRouter, createWebHistory } from 'vue-router'
import AppShell from './layouts/AppShell.vue'
import { useAuth } from './composables/useAuth'
import { getLocalizedRouteTitle } from './composables/useI18n'
import { hasRole, type AppRole } from './lib/permissions'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('./views/LoginView.vue'),
    meta: { titleKey: 'route.login', public: true },
  },
  {
    path: '/',
    component: AppShell,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('./views/DashboardView.vue'),
        meta: { titleKey: 'route.dashboard' },
      },
      {
        path: 'tasks',
        name: 'tasks',
        component: () => import('./views/TasksView.vue'),
        meta: { titleKey: 'route.tasks', roles: ['admin', 'operator', 'analyst'] },
      },
      {
        path: 'tasks/:taskId',
        name: 'task-detail',
        component: () => import('./views/TaskDetailView.vue'),
        meta: { titleKey: 'route.taskDetail', roles: ['admin', 'operator', 'analyst'] },
      },
      {
        path: 'datasets',
        name: 'datasets',
        component: () => import('./views/DatasetsView.vue'),
        meta: { titleKey: 'route.datasets' },
      },
      {
        path: 'datasets/:datasetId',
        name: 'dataset-detail',
        component: () => import('./views/DatasetDetailView.vue'),
        meta: { titleKey: 'route.datasetDetail' },
      },
      {
        path: 'analysis',
        name: 'analysis',
        component: () => import('./views/AnalysisView.vue'),
        meta: { titleKey: 'route.analysis' },
      },
      {
        path: 'signals',
        name: 'signals',
        component: () => import('./views/SignalsView.vue'),
        meta: { titleKey: 'route.signals' },
      },
      {
        path: 'signals/:signalId',
        name: 'signal-detail',
        component: () => import('./views/SignalDetailView.vue'),
        meta: { titleKey: 'route.signalDetail' },
      },
      {
        path: 'entities',
        name: 'entities',
        component: () => import('./views/EntitiesView.vue'),
        meta: { titleKey: 'route.entities' },
      },
      {
        path: 'cases',
        name: 'cases',
        component: () => import('./views/CasesView.vue'),
        meta: { titleKey: 'route.cases' },
      },
      {
        path: 'evidence',
        name: 'evidence',
        component: () => import('./views/EvidenceView.vue'),
        meta: { titleKey: 'route.evidence' },
      },
      {
        path: 'reports',
        name: 'reports',
        component: () => import('./views/ReportsView.vue'),
        meta: { titleKey: 'route.reports' },
      },
      {
        path: 'logs',
        name: 'logs',
        component: () => import('./views/LogsView.vue'),
        meta: { titleKey: 'route.logs', roles: ['admin', 'operator', 'analyst'] },
      },
      {
        path: 'settings',
        name: 'settings',
        component: () => import('./views/SettingsView.vue'),
        meta: { titleKey: 'route.settings', roles: ['admin', 'operator'] },
      },
      {
        path: 'help',
        name: 'help',
        component: () => import('./views/HelpView.vue'),
        meta: { titleKey: 'route.help' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuth()
  if (!auth.isReady.value) await auth.initializeAuth()

  if (!to.meta.public && !auth.user.value) {
    return {
      name: 'login',
      query: { redirect: to.fullPath },
    }
  }

  const roles = to.meta.roles as AppRole[] | undefined
  if (roles && !hasRole(auth.user.value, roles)) {
    return { name: 'dashboard' }
  }

  if (to.name === 'login' && auth.user.value) {
    return { name: 'dashboard' }
  }

  return true
})

router.afterEach((to) => {
  document.title = getLocalizedRouteTitle(to.meta.titleKey as string | undefined)
})

export default router
