<script setup lang="ts">
import { RouterLink, useRoute } from 'vue-router'

const route = useRoute()

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: 'D' },
  { to: '/tasks', label: 'Tasks', icon: 'T' },
  { to: '/datasets', label: 'Datasets', icon: 'DS' },
  { to: '/signals', label: 'Signals', icon: 'SI' },
  { to: '/entities', label: 'Entities', icon: 'E' },
  { to: '/cases', label: 'Cases', icon: 'C' },
  { to: '/evidence', label: 'Evidence', icon: 'EV' },
  { to: '/analysis', label: 'Analysis', icon: 'A' },
  { to: '/reports', label: 'Reports', icon: 'R' },
  { to: '/logs', label: 'Logs', icon: 'L' },
  { to: '/settings', label: 'Settings', icon: 'S' },
]
</script>

<template>
  <nav class="sidebar-nav">
    <RouterLink
      v-for="item in navItems"
      :key="item.to"
      :to="item.to"
      class="nav-btn"
      :class="{ active: route.path === item.to }"
    >
      <span class="nav-icon">{{ item.icon }}</span>
      <span>{{ item.label }}</span>
    </RouterLink>
  </nav>
</template>

<style scoped>
.sidebar-nav {
  display: grid;
  gap: 6px;
}

.nav-btn {
  position: relative;
  width: 100%;
  height: 52px;
  border-radius: 14px;
  border: 1px solid transparent;
  background: transparent;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 14px;
  color: #475569;
  font-weight: 700;
  transition: all 0.2s ease;
}

.nav-btn:hover {
  background: rgba(255, 255, 255, 0.72);
  color: #0f172a;
}

.nav-btn.active {
  background: linear-gradient(90deg, rgba(59, 130, 246, 0.12), rgba(59, 130, 246, 0.04));
  color: #0f172a;
  border-color: rgba(59, 130, 246, 0.12);
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
  background: #3b82f6;
}

.nav-icon {
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.76);
  font-size: 11px;
}
</style>
