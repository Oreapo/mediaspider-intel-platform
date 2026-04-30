import { createRouter, createWebHistory } from 'vue-router'
import AppShell from './layouts/AppShell.vue'

const routes = [
  {
    path: '/',
    component: AppShell,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'dashboard',
        component: () => import('./views/DashboardView.vue'),
        meta: { title: 'Dashboard' },
      },
      {
        path: 'tasks',
        name: 'tasks',
        component: () => import('./views/TasksView.vue'),
        meta: { title: 'Tasks' },
      },
      {
        path: 'datasets',
        name: 'datasets',
        component: () => import('./views/DatasetsView.vue'),
        meta: { title: 'Datasets' },
      },
      {
        path: 'analysis',
        name: 'analysis',
        component: () => import('./views/AnalysisView.vue'),
        meta: { title: 'Analysis' },
      },
      {
        path: 'signals',
        name: 'signals',
        component: () => import('./views/SignalsView.vue'),
        meta: { title: 'Signals' },
      },
      {
        path: 'entities',
        name: 'entities',
        component: () => import('./views/EntitiesView.vue'),
        meta: { title: 'Entities' },
      },
      {
        path: 'cases',
        name: 'cases',
        component: () => import('./views/CasesView.vue'),
        meta: { title: 'Cases' },
      },
      {
        path: 'evidence',
        name: 'evidence',
        component: () => import('./views/EvidenceView.vue'),
        meta: { title: 'Evidence' },
      },
      {
        path: 'reports',
        name: 'reports',
        component: () => import('./views/ReportsView.vue'),
        meta: { title: 'Reports' },
      },
      {
        path: 'logs',
        name: 'logs',
        component: () => import('./views/LogsView.vue'),
        meta: { title: 'Logs' },
      },
      {
        path: 'settings',
        name: 'settings',
        component: () => import('./views/SettingsView.vue'),
        meta: { title: 'Settings' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.afterEach((to) => {
  const appName = 'MediaSpider Intelligence Platform'
  document.title = to.meta.title ? `${String(to.meta.title)} - ${appName}` : appName
})

export default router
