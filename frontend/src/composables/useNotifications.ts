import { onMounted, ref } from 'vue'
import { listNotificationDeliveries, listNotificationRules } from '../api/notifications'
import type { NotificationDelivery, NotificationRule } from '../types'

export function useNotifications() {
  const rules = ref<NotificationRule[]>([])
  const deliveries = ref<NotificationDelivery[]>([])
  const isLoading = ref(false)
  const error = ref('')

  async function fetchItems() {
    isLoading.value = true
    error.value = ''
    try {
      const [ruleItems, deliveryItems] = await Promise.all([
        listNotificationRules(),
        listNotificationDeliveries(),
      ])
      rules.value = ruleItems
      deliveries.value = deliveryItems
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      isLoading.value = false
    }
  }

  onMounted(fetchItems)

  return { rules, deliveries, isLoading, error, fetchItems }
}
