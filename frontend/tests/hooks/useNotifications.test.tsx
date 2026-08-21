import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useNotifications } from '@/hooks/useNotifications'
import { useRealtimeStore, NotificationItem } from '@/stores/realtimeStore'

let mockLastMessage: any = null
vi.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: () => mockLastMessage,
}))
vi.mock('@/stores/authStore', () => ({
  useAuthStore: (selector: any) => selector({ user: { id: 'user-1' } }),
}))

describe('useNotifications', () => {
  beforeEach(() => {
    mockLastMessage = null
    useRealtimeStore.setState({ notifications: [] })
  })

  it('收到 notification 消息应追加到 store', () => {
    const { rerender } = renderHook(() => useNotifications())

    const notification: NotificationItem = {
      id: 'n-1',
      type: 'task_completed',
      title: '任务完成',
      body: '视频导出成功',
      createdAt: Date.now(),
      read: false,
    }

    mockLastMessage = { type: 'notification', data: notification }
    rerender()

    expect(useRealtimeStore.getState().notifications).toHaveLength(1)
    expect(useRealtimeStore.getState().notifications[0]).toEqual(notification)
  })

  it('非 notification 消息不应追加', () => {
    const { rerender } = renderHook(() => useNotifications())

    mockLastMessage = { type: 'progress', data: {} }
    rerender()

    expect(useRealtimeStore.getState().notifications).toHaveLength(0)
  })

  it('应返回 store 中的通知列表', () => {
    const notification: NotificationItem = {
      id: 'n-2',
      type: 'credit_low',
      title: '额度不足',
      body: '额度已用 80%',
      createdAt: Date.now(),
      read: false,
    }
    useRealtimeStore.setState({ notifications: [notification] })

    const { result } = renderHook(() => useNotifications())

    expect(result.current).toHaveLength(1)
    expect(result.current[0].id).toBe('n-2')
  })
})
