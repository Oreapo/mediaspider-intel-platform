import { reactive } from 'vue'
import { translate } from '../composables/useI18n'

type ConfirmTone = 'danger' | 'warning' | 'info'

export type ConfirmOptions = {
  title: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  tone?: ConfirmTone
}

type ConfirmState = ConfirmOptions & {
  open: boolean
  resolve?: (value: boolean) => void
}

export const confirmState = reactive<ConfirmState>({
  open: false,
  title: '',
  message: '',
  confirmLabel: translate('common.confirm'),
  cancelLabel: translate('common.cancel'),
  tone: 'danger',
})

export function requestConfirm(options: ConfirmOptions) {
  if (confirmState.resolve) {
    confirmState.resolve(false)
  }

  Object.assign(confirmState, {
    open: true,
    title: options.title,
    message: options.message,
    confirmLabel: options.confirmLabel || translate('common.confirm'),
    cancelLabel: options.cancelLabel || translate('common.cancel'),
    tone: options.tone || 'danger',
  })

  return new Promise<boolean>((resolve) => {
    confirmState.resolve = resolve
  })
}

export function settleConfirm(value: boolean) {
  confirmState.open = false
  confirmState.resolve?.(value)
  confirmState.resolve = undefined
}
