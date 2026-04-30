<script setup lang="ts">
import { computed } from 'vue'
import { usePlatformModels } from '../composables/usePlatformModels'
import { useTasks } from '../composables/useTasks'
import { useDatasets } from '../composables/useDatasets'
import { useAnalysisJobs } from '../composables/useAnalysisJobs'

const { items: platformItems, isLoading: platformsLoading, error: platformsError } = usePlatformModels()
const { items: taskItems } = useTasks()
const { items: datasetItems } = useDatasets()
const { items: analysisJobItems } = useAnalysisJobs()

const stats = computed(() => [
  {
    label: 'Platform Models',
    value: platformItems.value.length,
    hint: '平台能力模板',
  },
  {
    label: 'Tasks',
    value: taskItems.value.length,
    hint: '已登记采集任务',
  },
  {
    label: 'Datasets',
    value: datasetItems.value.length,
    hint: '可供分析的数据集',
  },
  {
    label: 'Analysis Jobs',
    value: analysisJobItems.value.length,
    hint: '已生成分析任务',
  },
])

const latestTasks = computed(() => taskItems.value.slice(0, 5))
const latestDatasets = computed(() => datasetItems.value.slice(0, 5))
const latestJobs = computed(() => analysisJobItems.value.slice(0, 5))
</script>

<template>
  <section class="page-grid">
    <div class="stats-grid">
      <article v-for="stat in stats" :key="stat.label" class="surface stat-card">
        <span class="eyebrow">{{ stat.label }}</span>
        <strong>{{ stat.value }}</strong>
        <p>{{ stat.hint }}</p>
      </article>
    </div>

    <div class="overview-grid">
      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Platform Coverage</h2>
            <p>当前规划的多平台采集能力模板。</p>
          </div>
        </div>
        <div v-if="platformsLoading" class="muted">Loading platform models...</div>
        <div v-else-if="platformsError" class="muted">{{ platformsError }}</div>
        <div v-else class="chip-grid">
          <article v-for="item in platformItems" :key="item.platform" class="chip-card">
            <strong>{{ item.label }}</strong>
            <span>{{ item.summary }}</span>
          </article>
        </div>
      </section>

      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Recent Tasks</h2>
            <p>采集任务是数据与分析链路的入口。</p>
          </div>
        </div>
        <div class="compact-list">
          <article v-for="item in latestTasks" :key="item.id" class="compact-item">
            <strong>{{ item.task_name }}</strong>
            <span>{{ item.platform }} · {{ item.entity_type }} · {{ item.status }}</span>
          </article>
          <div v-if="!latestTasks.length" class="muted">No tasks yet.</div>
        </div>
      </section>
    </div>

    <div class="overview-grid">
      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Recent Datasets</h2>
            <p>数据集是情报分析的中心对象。</p>
          </div>
        </div>
        <div class="compact-list">
          <article v-for="item in latestDatasets" :key="item.id" class="compact-item">
            <strong>{{ item.dataset_name }}</strong>
            <span>{{ item.source_platform }} · {{ item.dataset_type }} · {{ item.record_count }} records</span>
          </article>
          <div v-if="!latestDatasets.length" class="muted">No datasets yet.</div>
        </div>
      </section>

      <section class="surface section-card">
        <div class="section-head">
          <div>
            <h2>Recent Analysis Jobs</h2>
            <p>分析结果会沉淀成平台洞察和跨平台情报。</p>
          </div>
        </div>
        <div class="compact-list">
          <article v-for="item in latestJobs" :key="item.id" class="compact-item">
            <strong>{{ item.analysis_type }}</strong>
            <span>{{ item.analysis_scope }} · {{ item.status }}</span>
          </article>
          <div v-if="!latestJobs.length" class="muted">No analysis jobs yet.</div>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.page-grid {
  display: grid;
  gap: 18px;
}

.stats-grid,
.overview-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.stats-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.stat-card,
.section-card {
  border-radius: 24px;
  padding: 22px;
}

.eyebrow {
  display: block;
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #64748b;
}

.stat-card strong {
  display: block;
  font-size: 36px;
  line-height: 1;
  margin-bottom: 8px;
}

.stat-card p,
.section-head p,
.muted,
.compact-item span,
.chip-card span {
  color: #64748b;
}

.section-head {
  margin-bottom: 16px;
}

.section-head h2 {
  margin: 0 0 6px;
}

.chip-grid,
.compact-list {
  display: grid;
  gap: 12px;
}

.chip-card,
.compact-item {
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(248, 250, 252, 0.84);
}

.chip-card strong,
.compact-item strong {
  display: block;
  margin-bottom: 6px;
}

@media (max-width: 1280px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 920px) {
  .overview-grid,
  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
