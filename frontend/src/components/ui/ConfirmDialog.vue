<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import { confirmState, settleConfirm } from '../../lib/confirm'

function close() {
  settleConfirm(false)
}

function confirm() {
  settleConfirm(true)
}

function onKeydown(event: KeyboardEvent) {
  if (!confirmState.open) return
  if (event.key === 'Escape') close()
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <Transition name="confirm-fade">
      <div v-if="confirmState.open" class="confirm-backdrop" role="presentation" @click.self="close">
        <section
          class="confirm-dialog"
          :class="confirmState.tone"
          aria-modal="true"
          role="dialog"
          aria-labelledby="confirm-title"
          aria-describedby="confirm-message"
        >
          <div class="confirm-head">
            <span class="confirm-mark" aria-hidden="true" />
            <div>
              <h2 id="confirm-title">{{ confirmState.title }}</h2>
              <p id="confirm-message">{{ confirmState.message }}</p>
            </div>
          </div>

          <div class="confirm-actions">
            <button class="ghost-button" type="button" @click="close">
              {{ confirmState.cancelLabel }}
            </button>
            <button class="confirm-button" type="button" autofocus @click="confirm">
              {{ confirmState.confirmLabel }}
            </button>
          </div>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.confirm-backdrop {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.38);
  backdrop-filter: blur(10px);
}

.confirm-dialog {
  width: min(100%, 460px);
  overflow: hidden;
  border: 1px solid rgba(190, 202, 216, 0.82);
  border-radius: calc(var(--radius) + 2px);
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.92)),
    white;
  box-shadow: 0 26px 70px rgba(15, 23, 42, 0.28);
}

.confirm-head {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 14px;
  padding: 22px;
}

.confirm-mark {
  width: 12px;
  height: 38px;
  border-radius: 999px;
  background: #dc2626;
  box-shadow: 0 0 0 5px rgba(220, 38, 38, 0.1);
}

.confirm-dialog.warning .confirm-mark {
  background: #d97706;
  box-shadow: 0 0 0 5px rgba(217, 119, 6, 0.12);
}

.confirm-dialog.info .confirm-mark {
  background: #2563eb;
  box-shadow: 0 0 0 5px rgba(37, 99, 235, 0.12);
}

.confirm-head h2 {
  margin: 0 0 8px;
  color: var(--foreground);
  font-size: 19px;
  letter-spacing: 0;
}

.confirm-head p {
  margin: 0;
  color: #475569;
  line-height: 1.65;
  overflow-wrap: anywhere;
}

.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 18px 18px;
  border-top: 1px solid rgba(226, 232, 240, 0.86);
  background: rgba(248, 250, 252, 0.74);
}

.ghost-button,
.confirm-button {
  border: none;
  border-radius: var(--radius);
  padding: 10px 14px;
  font-weight: 800;
  cursor: pointer;
}

.ghost-button {
  background: rgba(226, 232, 240, 0.92);
  color: #1e293b;
}

.confirm-button {
  background: #dc2626;
  color: white;
}

.confirm-dialog.warning .confirm-button {
  background: #d97706;
}

.confirm-dialog.info .confirm-button {
  background: #2563eb;
}

.confirm-fade-enter-active,
.confirm-fade-leave-active {
  transition: opacity 0.16s ease;
}

.confirm-fade-enter-active .confirm-dialog,
.confirm-fade-leave-active .confirm-dialog {
  transition: transform 0.16s ease;
}

.confirm-fade-enter-from,
.confirm-fade-leave-to {
  opacity: 0;
}

.confirm-fade-enter-from .confirm-dialog,
.confirm-fade-leave-to .confirm-dialog {
  transform: translateY(8px) scale(0.98);
}

@media (max-width: 540px) {
  .confirm-backdrop {
    align-items: end;
    padding: 14px;
  }

  .confirm-actions {
    display: grid;
  }
}
</style>
