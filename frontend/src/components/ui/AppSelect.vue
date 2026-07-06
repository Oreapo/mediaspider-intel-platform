<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import PlatformLogo from './PlatformLogo.vue'

type OptionValue = string | number

interface SelectOption {
  value: OptionValue
  label: string
  disabled?: boolean
  hint?: string
  /** When set, renders the platform logo (via PlatformLogo) beside the label. */
  platform?: string
}

const props = withDefaults(
  defineProps<{
    modelValue: OptionValue
    options: SelectOption[]
    placeholder?: string
    disabled?: boolean
    size?: 'sm' | 'md'
    ariaLabel?: string
  }>(),
  {
    placeholder: '',
    disabled: false,
    size: 'md',
  },
)

const emit = defineEmits<{
  (event: 'update:modelValue', value: OptionValue): void
  (event: 'change', value: OptionValue): void
}>()

const open = ref(false)
const activeIndex = ref(-1)
const triggerRef = ref<HTMLButtonElement | null>(null)
const panelRef = ref<HTMLDivElement | null>(null)
const panelStyle = ref<Record<string, string>>({})
const dropUp = ref(false)

const selectedOption = computed(() =>
  props.options.find((option) => option.value === props.modelValue),
)
const displayLabel = computed(() => selectedOption.value?.label ?? props.placeholder)
const hasValue = computed(() => selectedOption.value !== undefined)

function updatePosition() {
  const trigger = triggerRef.value
  if (!trigger) return
  const rect = trigger.getBoundingClientRect()
  const spaceBelow = window.innerHeight - rect.bottom
  const estimated = Math.min(props.options.length * 40 + 12, 288)
  dropUp.value = spaceBelow < estimated + 16 && rect.top > spaceBelow
  panelStyle.value = {
    position: 'fixed',
    left: `${rect.left}px`,
    minWidth: `${rect.width}px`,
    ...(dropUp.value
      ? { bottom: `${window.innerHeight - rect.top + 6}px` }
      : { top: `${rect.bottom + 6}px` }),
  }
}

async function openMenu() {
  if (props.disabled) return
  open.value = true
  activeIndex.value = props.options.findIndex((option) => option.value === props.modelValue)
  await nextTick()
  updatePosition()
  scrollActiveIntoView()
}

function closeMenu() {
  open.value = false
  activeIndex.value = -1
}

function toggleMenu() {
  if (open.value) closeMenu()
  else void openMenu()
}

function selectOption(option: SelectOption) {
  if (option.disabled) return
  emit('update:modelValue', option.value)
  emit('change', option.value)
  closeMenu()
  triggerRef.value?.focus()
}

function moveActive(step: number) {
  const count = props.options.length
  if (!count) return
  let next = activeIndex.value
  for (let i = 0; i < count; i += 1) {
    next = (next + step + count) % count
    if (!props.options[next]?.disabled) break
  }
  activeIndex.value = next
  scrollActiveIntoView()
}

function scrollActiveIntoView() {
  void nextTick(() => {
    panelRef.value
      ?.querySelector('.is-active')
      ?.scrollIntoView({ block: 'nearest' })
  })
}

function onKeydown(event: KeyboardEvent) {
  if (props.disabled) return
  if (!open.value) {
    if (['Enter', ' ', 'ArrowDown', 'ArrowUp'].includes(event.key)) {
      event.preventDefault()
      void openMenu()
    }
    return
  }
  switch (event.key) {
    case 'ArrowDown':
      event.preventDefault()
      moveActive(1)
      break
    case 'ArrowUp':
      event.preventDefault()
      moveActive(-1)
      break
    case 'Enter':
    case ' ':
      event.preventDefault()
      if (activeIndex.value >= 0) selectOption(props.options[activeIndex.value])
      break
    case 'Escape':
      event.preventDefault()
      closeMenu()
      break
    case 'Tab':
      closeMenu()
      break
    default:
      break
  }
}

function onDocumentPointer(event: PointerEvent) {
  const target = event.target as Node
  if (triggerRef.value?.contains(target) || panelRef.value?.contains(target)) return
  closeMenu()
}

function onViewportChange() {
  if (open.value) closeMenu()
}

watch(open, (isOpen) => {
  if (isOpen) {
    document.addEventListener('pointerdown', onDocumentPointer, true)
    window.addEventListener('scroll', onViewportChange, true)
    window.addEventListener('resize', onViewportChange)
  } else {
    document.removeEventListener('pointerdown', onDocumentPointer, true)
    window.removeEventListener('scroll', onViewportChange, true)
    window.removeEventListener('resize', onViewportChange)
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onDocumentPointer, true)
  window.removeEventListener('scroll', onViewportChange, true)
  window.removeEventListener('resize', onViewportChange)
})
</script>

<template>
  <div class="app-select" :class="[size, { open, disabled }]">
    <button
      ref="triggerRef"
      type="button"
      class="app-select-trigger"
      role="combobox"
      aria-haspopup="listbox"
      :aria-expanded="open"
      :aria-label="ariaLabel"
      :disabled="disabled"
      @click="toggleMenu"
      @keydown="onKeydown"
    >
      <span class="app-select-value" :class="{ placeholder: !hasValue }">
        <PlatformLogo v-if="selectedOption?.platform" :platform="selectedOption.platform" :size="18" />
        <span class="app-select-value-text">{{ displayLabel }}</span>
      </span>
      <svg
        class="app-select-caret"
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.4"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <path d="m6 9 6 6 6-6" />
      </svg>
    </button>

    <Teleport to="body">
      <div
        v-if="open"
        ref="panelRef"
        class="app-select-panel"
        :class="{ up: dropUp }"
        :style="panelStyle"
        role="listbox"
      >
        <button
            v-for="(option, index) in options"
            :key="option.value"
            type="button"
            class="app-select-option"
            :class="{
              'is-selected': option.value === modelValue,
              'is-active': index === activeIndex,
              'is-disabled': option.disabled,
            }"
            role="option"
            :aria-selected="option.value === modelValue"
            :disabled="option.disabled"
            @click="selectOption(option)"
            @mousemove="activeIndex = index"
          >
            <PlatformLogo
              v-if="option.platform"
              class="option-logo"
              :platform="option.platform"
              :size="18"
            />
            <span class="option-body">
              <span class="option-label">{{ option.label }}</span>
              <span v-if="option.hint" class="option-hint">{{ option.hint }}</span>
            </span>
            <svg
              v-if="option.value === modelValue"
              class="option-check"
              width="15"
              height="15"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="3"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <path d="M20 6 9 17l-5-5" />
            </svg>
          </button>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.app-select {
  position: relative;
  display: inline-flex;
  width: 100%;
}

.app-select-trigger {
  width: 100%;
  min-height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 12px;
  border-radius: var(--radius);
  border: 1px solid color-mix(in oklch, var(--primary) 12%, var(--border));
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.7), rgba(255, 255, 255, 0.42)),
    color-mix(in oklch, var(--primary) 3%, var(--card-strong));
  color: var(--foreground);
  font: inherit;
  font-weight: 700;
  cursor: pointer;
  transition:
    border-color 160ms ease,
    box-shadow 180ms ease,
    background 180ms ease;
}

.app-select.sm .app-select-trigger {
  min-height: 34px;
  padding: 6px 10px;
  font-size: 13px;
}

.app-select-trigger:hover:not(:disabled) {
  border-color: color-mix(in oklch, var(--primary) 42%, var(--border));
}

.app-select.open .app-select-trigger,
.app-select-trigger:focus-visible {
  outline: none;
  border-color: color-mix(in oklch, var(--primary) 62%, transparent);
  box-shadow: 0 0 0 3px color-mix(in oklch, var(--primary) 15%, transparent);
}

.app-select.disabled {
  opacity: 0.6;
}

.app-select.disabled .app-select-trigger {
  cursor: not-allowed;
}

.app-select-value {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.app-select-value-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-select-value.placeholder {
  color: var(--muted-foreground);
  font-weight: 600;
}

.app-select-caret {
  flex-shrink: 0;
  color: color-mix(in oklch, var(--primary) 55%, var(--muted-foreground));
  transition: transform 200ms ease;
}

.app-select.open .app-select-caret {
  transform: rotate(180deg);
}
</style>

<style>
/* Panel is teleported to <body>, so it lives outside scoped styles. */
.app-select-panel {
  z-index: 1200;
  max-height: 288px;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 6px;
  border-radius: var(--radius);
  border: 1px solid color-mix(in oklch, var(--primary) 26%, var(--border));
  background: color-mix(in oklch, var(--card-strong) 88%, transparent);
  backdrop-filter: blur(22px) saturate(1.3);
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.6) inset,
    0 24px 48px -20px var(--brand-glow),
    0 8px 20px -14px rgba(15, 23, 42, 0.4);
  animation: app-select-in 150ms ease both;
  transform-origin: top center;
}

.app-select-panel.up {
  transform-origin: bottom center;
  animation-name: app-select-in-up;
}

@keyframes app-select-in {
  from {
    opacity: 0;
    transform: translateY(-6px) scale(0.98);
  }

  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes app-select-in-up {
  from {
    opacity: 0;
    transform: translateY(6px) scale(0.98);
  }

  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.app-select-panel::before {
  content: "";
  display: block;
  height: 2px;
  margin: -2px -2px 6px;
  border-radius: 999px;
  background: linear-gradient(90deg, transparent, var(--primary), transparent);
  opacity: 0.55;
}

.app-select-option {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 9px 10px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--foreground);
  font: inherit;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
  transition: background 120ms ease, color 120ms ease;
}

.app-select-option .option-logo {
  flex-shrink: 0;
}

.app-select-option .option-body {
  display: grid;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.app-select-option .option-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-select-option .option-hint {
  font-size: 11px;
  font-weight: 600;
  color: var(--muted-foreground);
}

.app-select-option.is-active {
  background: color-mix(in oklch, var(--primary) 12%, transparent);
}

.app-select-option.is-selected {
  color: var(--primary);
  font-weight: 800;
  background: color-mix(in oklch, var(--primary) 9%, transparent);
}

.app-select-option.is-selected.is-active {
  background: color-mix(in oklch, var(--primary) 16%, transparent);
}

.app-select-option .option-check {
  flex-shrink: 0;
  color: var(--primary);
}

.app-select-option.is-disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

@media (prefers-reduced-motion: reduce) {
  .app-select-panel {
    animation: none;
  }

  .app-select-caret {
    transition: none;
  }
}
</style>
