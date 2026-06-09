import { onMounted, ref } from 'vue'
import {
  listNotificationDeliveries,
  listNotificationInbox,
  listNotificationRules,
  type NotificationDeliveryQuery,
  type NotificationInboxQuery,
} from '../api/notifications'
import type { NotificationDelivery, NotificationInboxItem, NotificationRule } from '../types'

export function useNotifications() {
  const rules = ref<NotificationRule[]>([])
  const deliveries = ref<NotificationDelivery[]>([])
  const inbox = ref<NotificationInboxItem[]>([])
  const unreadCount = ref(0)
  const deliveryQuery = ref<NotificationDeliveryQuery>({
    limit: 20,
    offset: 0,
  })
  const inboxQuery = ref<NotificationInboxQuery>({
    limit: 20,
    offset: 0,
  })
  const isLoading = ref(false)
  const error = ref('')

  async function fetchItems() {
    isLoading.value = true
    error.value = ''
    try {
      const [ruleItems, deliveryItems, inboxItems] = await Promise.all([
        listNotificationRules(),
        listNotificationDeliveries(deliveryQuery.value),
        listNotificationInbox(inboxQuery.value),
      ])
      rules.value = ruleItems
      deliveries.value = deliveryItems
      inbox.value = inboxItems.items
      unreadCount.value = inboxItems.unread_count
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
    } finally {
      isLoading.value = false
    }
  }

  onMounted(fetchItems)

  function updateDeliveryQuery(query: Partial<NotificationDeliveryQuery>) {
    deliveryQuery.value = {
      ...deliveryQuery.value,
      ...query,
    }
    return fetchItems()
  }

  function updateInboxQuery(query: Partial<NotificationInboxQuery>) {
    inboxQuery.value = {
      ...inboxQuery.value,
      ...query,
    }
    return fetchItems()
  }

  return {
    rules,
    deliveries,
    inbox,
    unreadCount,
    deliveryQuery,
    inboxQuery,
    isLoading,
    error,
    fetchItems,
    updateDeliveryQuery,
    updateInboxQuery,
  }
}
