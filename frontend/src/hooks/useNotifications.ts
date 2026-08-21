import { useEffect } from 'react'
import { useWebSocket } from './useWebSocket'
import { useRealtimeStore, NotificationItem } from '@/stores/realtimeStore'
import { useAuthStore } from '@/stores/authStore'

/**
 * 订阅用户通知频道
 * 返回当前通知列表
 */
export function useNotifications() {
  const userId = useAuthStore((s) => s.user?.id)
  const lastMsg = useWebSocket(userId ? `user:${userId}` : null)

  useEffect(() => {
    if (!lastMsg) return

    if (lastMsg.type === 'notification' && lastMsg.data) {
      const notification = lastMsg.data as NotificationItem
      useRealtimeStore.getState().addNotification(notification)

      // Desktop 系统通知
      window.electronAPI?.showNotification?.(notification)

      // Web 浏览器通知（需用户授权）
      if (!window.electronAPI && 'Notification' in window && Notification.permission === 'granted') {
        new Notification(notification.title, { body: notification.body })
      }
    }
  }, [lastMsg])

  return useRealtimeStore((s) => s.notifications)
}
