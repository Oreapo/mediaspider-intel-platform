<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import TheSidebar from '../components/layout/TheSidebar.vue'
import TheHeader from '../components/layout/TheHeader.vue'

const route = useRoute()

const pageMeta = computed(() => {
  const lookup: Record<string, { title: string; description: string }> = {
    '/dashboard': {
      title: 'Dashboard',
      description: '平台接入状态、最新数据集、最近分析和运行活动概览。',
    },
    '/tasks': {
      title: 'Tasks',
      description: '围绕统一任务模型管理多平台采集任务和运行策略。',
    },
    '/datasets': {
      title: 'Datasets',
      description: '把采集结果沉淀成可预览、可筛选、可分析的数据集。',
    },
    '/analysis': {
      title: 'Analysis',
      description: '通用分析、平台专属分析和跨平台情报分析中心。',
    },
    '/signals': {
      title: 'Signals',
      description: '从数据集提取、复核和确认可追溯的风险信号。',
    },
    '/entities': {
      title: 'Entities',
      description: '把信号聚合成账号、商品、卖家、联系方式等风险对象与关系。',
    },
    '/cases': {
      title: 'Cases',
      description: '把数据集、信号、实体、分析输出和备注组织成可持续追踪的案件。',
    },
    '/evidence': {
      title: 'Evidence',
      description: '从案件生成可下载、可追溯的证据包 manifest。',
    },
    '/reports': {
      title: 'Reports',
      description: '将数据集和分析结果进一步沉淀为情报报告。',
    },
    '/logs': {
      title: 'Logs',
      description: '统一查看任务运行日志、错误诊断与执行历史。',
    },
    '/settings': {
      title: 'Settings',
      description: '平台接入、登录态、存储、通知和分析配置。',
    },
  }
  return lookup[route.path] ?? lookup['/dashboard']
})
</script>

<template>
  <div class="shell">
    <TheHeader />
    <div class="content-wrap">
      <aside class="sidebar">
        <div class="sidebar-inner">
          <TheSidebar />
          <section class="sidebar-status surface-subtle">
            <small>Product Focus</small>
            <div class="sidebar-status-row">
              <span class="status-dot" />
              <span>Collection + Dataset + Signals</span>
            </div>
          </section>
        </div>
      </aside>

      <main class="main">
        <div class="main-inner">
          <section class="page-hero surface">
            <div class="page-title">
              <h1>{{ pageMeta.title }}</h1>
              <div class="page-desc">{{ pageMeta.description }}</div>
            </div>
          </section>

          <RouterView />
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.content-wrap {
  display: flex;
  min-height: calc(100vh - 72px);
}

.sidebar {
  width: 264px;
  flex-shrink: 0;
  border-right: 1px solid rgba(226, 232, 240, 0.8);
  background: rgba(255, 255, 255, 0.42);
  backdrop-filter: blur(8px);
}

.sidebar-inner {
  position: sticky;
  top: 72px;
  height: calc(100vh - 72px);
  padding: 18px 16px;
  display: grid;
  align-content: start;
  gap: 18px;
}

.sidebar-status {
  margin-top: 18px;
  padding: 16px;
  border-radius: 18px;
}

.sidebar-status small {
  display: block;
  margin-bottom: 8px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #94a3b8;
}

.sidebar-status-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  font-weight: 700;
}

.status-dot {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: #10b981;
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.12);
}

.main {
  flex: 1;
  min-width: 0;
  padding: 24px;
}

.main-inner {
  max-width: 1440px;
  margin: 0 auto;
  display: grid;
  gap: 18px;
}

.page-hero {
  border-radius: 26px;
  padding: 24px;
}

.page-title {
  display: grid;
  gap: 8px;
}

.page-title h1 {
  margin: 0;
  font-size: 40px;
  letter-spacing: -0.05em;
}

.page-desc {
  color: #64748b;
  font-size: 15px;
  line-height: 1.6;
}

@media (max-width: 980px) {
  .content-wrap {
    display: block;
  }

  .sidebar {
    width: 100%;
    border-right: none;
    border-bottom: 1px solid rgba(226, 232, 240, 0.8);
  }

  .sidebar-inner {
    position: static;
    height: auto;
  }

  .main {
    padding: 16px;
  }
}
</style>
