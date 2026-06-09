<script setup lang="ts">
import { computed } from 'vue'
import BaseSection from '../components/ui/BaseSection.vue'
import { useI18n } from '../composables/useI18n'

const { t } = useI18n()

const workflowKeys = ['tasks', 'datasets', 'signals', 'entities', 'cases', 'delivery']
const moduleKeys = [
  ['dashboard', '/dashboard'],
  ['tasks', '/tasks'],
  ['datasets', '/datasets'],
  ['analysis', '/analysis'],
  ['signals', '/signals'],
  ['entities', '/entities'],
  ['cases', '/cases'],
  ['evidence', '/evidence'],
  ['reports', '/reports'],
  ['logs', '/logs'],
  ['settings', '/settings'],
] as const
const startupKeys = ['backend', 'frontend']
const faqKeys = ['dashboardEmpty', 'runFailed', 'signalEmpty', 'evidenceWhen']

const workflowSteps = computed(() =>
  workflowKeys.map((key) => ({
    title: t(`help.workflow.${key}.title`),
    text: t(`help.workflow.${key}.text`),
  })),
)

const moduleGuides = computed(() =>
  moduleKeys.map(([key, path]) => ({
    title: t(`help.module.${key}.title`),
    path,
    summary: t(`help.module.${key}.summary`),
    actions: [1, 2, 3].map((index) => t(`help.module.${key}.action${index}`)),
  })),
)

const startupCommands = computed(() =>
  startupKeys.map((key) => ({
    title: t(`help.startup.${key}.title`),
    command:
      key === 'backend'
        ? '.venv\\Scripts\\python.exe -m backend.app'
        : 'cd frontend\nnpm install\nnpm run dev',
    hint: t(`help.startup.${key}.hint`),
  })),
)

const faqItems = computed(() =>
  faqKeys.map((key) => ({
    question: t(`help.faq.${key}.question`),
    answer: t(`help.faq.${key}.answer`),
  })),
)
</script>

<template>
  <section class="help-page">
    <BaseSection class="guide-intro">
      <div>
        <span class="eyebrow">{{ t('help.eyebrow') }}</span>
        <h2>{{ t('help.title') }}</h2>
        <p>{{ t('help.description') }}</p>
      </div>
      <div class="intro-note">
        <strong>{{ t('help.recommendedOrder') }}</strong>
        <span>{{ t('help.recommendedFlow') }}</span>
      </div>
    </BaseSection>

    <BaseSection :title="t('help.workflowTitle')" :description="t('help.workflowDescription')">
      <div class="workflow-grid">
        <article v-for="(step, index) in workflowSteps" :key="step.title" class="workflow-step">
          <span>{{ index + 1 }}</span>
          <strong>{{ step.title }}</strong>
          <p>{{ step.text }}</p>
        </article>
      </div>
    </BaseSection>

    <BaseSection :title="t('help.modulesTitle')" :description="t('help.modulesDescription')">
      <div class="module-grid">
        <article v-for="item in moduleGuides" :key="item.path" class="module-card">
          <div class="module-head">
            <h3>{{ item.title }}</h3>
            <RouterLink :to="item.path">{{ t('help.enter') }}</RouterLink>
          </div>
          <p>{{ item.summary }}</p>
          <ul>
            <li v-for="action in item.actions" :key="action">{{ action }}</li>
          </ul>
        </article>
      </div>
    </BaseSection>

    <section class="split-grid">
      <BaseSection :title="t('help.startupTitle')" :description="t('help.startupDescription')">
        <article v-for="item in startupCommands" :key="item.title" class="command-card">
          <strong>{{ item.title }}</strong>
          <pre>{{ item.command }}</pre>
          <p>{{ item.hint }}</p>
        </article>
      </BaseSection>

      <BaseSection :title="t('help.faqTitle')" :description="t('help.faqDescription')">
        <div class="faq-list">
          <article v-for="item in faqItems" :key="item.question" class="faq-item">
            <strong>{{ item.question }}</strong>
            <p>{{ item.answer }}</p>
          </article>
        </div>
      </BaseSection>
    </section>
  </section>
</template>

<style scoped>
.help-page {
  display: grid;
  gap: 18px;
}

.guide-intro {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 0.44fr);
  gap: 24px;
  align-items: center;
}

.eyebrow {
  display: block;
  margin-bottom: 8px;
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0;
}

.guide-intro h2,
.module-head h3 {
  margin: 0;
}

.guide-intro h2 {
  margin-bottom: 10px;
  font-size: 30px;
}

.guide-intro p,
.module-card p,
.command-card p,
.faq-item p,
.intro-note span {
  color: #64748b;
  line-height: 1.65;
}

.intro-note {
  display: grid;
  gap: 8px;
  padding: 18px;
  border-radius: var(--radius);
  border: 1px solid rgba(59, 130, 246, 0.18);
  background: rgba(239, 246, 255, 0.72);
}

.workflow-grid,
.module-grid {
  display: grid;
  gap: 14px;
}

.workflow-grid {
  grid-template-columns: repeat(6, minmax(0, 1fr));
}

.module-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.workflow-step,
.module-card,
.command-card,
.faq-item {
  border-radius: var(--radius);
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(248, 250, 252, 0.82);
}

.workflow-step {
  display: grid;
  gap: 8px;
  min-height: 170px;
  padding: 16px;
}

.workflow-step span {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border-radius: var(--radius);
  background: rgba(59, 130, 246, 0.12);
  color: #2563eb;
  font-weight: 800;
}

.workflow-step p {
  margin: 0;
  color: #64748b;
  line-height: 1.55;
}

.module-card {
  padding: 16px;
}

.module-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 10px;
}

.module-head a {
  color: #2563eb;
  font-size: 13px;
  font-weight: 800;
  text-decoration: none;
}

.module-card ul {
  margin: 12px 0 0;
  padding-left: 18px;
  color: #334155;
}

.module-card li + li {
  margin-top: 6px;
}

.split-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 18px;
}

.command-card {
  padding: 16px;
}

.command-card + .command-card {
  margin-top: 14px;
}

pre {
  margin: 12px 0;
  padding: 14px;
  overflow: auto;
  border-radius: var(--radius);
  background: #0f172a;
  color: #e2e8f0;
  white-space: pre-wrap;
}

.faq-list {
  display: grid;
  gap: 12px;
}

.faq-item {
  padding: 16px;
}

.faq-item p {
  margin-bottom: 0;
}

@media (max-width: 1280px) {
  .workflow-grid,
  .module-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 920px) {
  .guide-intro,
  .workflow-grid,
  .module-grid,
  .split-grid {
    grid-template-columns: 1fr;
  }
}
</style>
