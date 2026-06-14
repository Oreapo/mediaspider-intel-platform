<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import TheSidebar from '../components/layout/TheSidebar.vue'
import TheHeader from '../components/layout/TheHeader.vue'
import ConfirmDialog from '../components/ui/ConfirmDialog.vue'

const route = useRoute()

const pageMeta = computed(() => {
  const lookup: Record<string, { title: string; description: string }> = {
    '/dashboard': {
      title: '首页看板',
      description: '从采集、复核、调查到交付的全链路工作台。',
    },
    '/tasks': {
      title: '采集任务',
      description: '围绕统一任务模型管理多平台采集任务和运行策略。',
    },
    '/datasets': {
      title: '数据集',
      description: '把采集结果沉淀成可预览、可筛选、可分析的数据集。',
    },
    '/analysis': {
      title: '情报分析',
      description: '通用分析、平台专属分析和跨平台情报分析中心。',
    },
    '/signals': {
      title: '风险信号',
      description: '从数据集提取、复核和确认可追溯的风险信号。',
    },
    '/entities': {
      title: '风险实体',
      description: '把信号聚合成账号、商品、卖家、联系方式等风险对象与关系。',
    },
    '/cases': {
      title: '案件',
      description: '把数据集、信号、实体、分析输出和备注组织成可持续追踪的案件。',
    },
    '/evidence': {
      title: '证据包',
      description: '从案件生成可下载、可追溯的证据包 manifest。',
    },
    '/reports': {
      title: '报告',
      description: '将数据集和分析结果进一步沉淀为情报报告。',
    },
    '/logs': {
      title: '日志',
      description: '统一查看任务运行日志、错误诊断与执行历史。',
    },
    '/settings': {
      title: '设置',
      description: '平台接入、登录态、存储、通知和分析配置。',
    },
    '/help': {
      title: '使用说明',
      description: '查看平台工作流、功能模块、启动方式和常见问题。',
    },
  }
  const matchedPath = Object.keys(lookup)
    .filter((path) => route.path === path || route.path.startsWith(`${path}/`))
    .sort((left, right) => right.length - left.length)[0]
  return lookup[matchedPath] ?? lookup['/dashboard']
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
            <small>当前能力</small>
            <div class="sidebar-status-row">
              <span class="status-dot" />
              <span>采集 + 复核 + 案件交付</span>
            </div>
            <div class="sidebar-metric">
              <span>INTEL FLOW</span>
              <strong>ONLINE</strong>
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
    <ConfirmDialog />
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
  min-height: calc(100vh - 64px);
}

.sidebar {
  width: 284px;
  flex-shrink: 0;
  border-right: 1px solid rgba(24, 45, 68, 0.12);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.82), rgba(244, 248, 251, 0.72)),
    linear-gradient(90deg, rgba(29, 78, 116, 0.025) 1px, transparent 1px);
  background-size: auto, 22px 22px;
  backdrop-filter: blur(16px);
}

.sidebar-inner {
  position: sticky;
  top: 64px;
  height: calc(100vh - 64px);
  padding: 16px 14px;
  display: grid;
  align-content: start;
  gap: 16px;
  overflow-y: auto;
  overscroll-behavior: contain;
}

.sidebar-status {
  margin-top: 14px;
  padding: 14px;
  border-radius: var(--radius);
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

.sidebar-metric {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid rgba(190, 202, 216, 0.72);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.sidebar-metric span {
  color: #64748b;
  font-size: 11px;
  font-weight: 800;
}

.sidebar-metric strong {
  color: #0f766e;
  font-size: 12px;
}

.main {
  flex: 1;
  min-width: 0;
  padding: 22px 24px 32px;
}

.main-inner {
  width: min(100%, 1760px);
  margin: 0;
  display: grid;
  gap: 16px;
}

.page-hero {
  position: relative;
  overflow: hidden;
  border-radius: var(--radius);
  padding: 18px 22px;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(246, 250, 253, 0.88)),
    var(--card);
}

.page-hero::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 5px;
  background: linear-gradient(180deg, var(--primary), var(--accent));
}

.page-title {
  display: grid;
  gap: 8px;
}

.page-title h1 {
  margin: 0;
  font-size: clamp(24px, 2vw, 32px);
  letter-spacing: 0;
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
    padding: 14px;
  }
}
</style>
