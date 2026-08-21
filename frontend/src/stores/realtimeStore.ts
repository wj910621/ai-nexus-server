import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { WSStatus } from '@/api/websocket'

export interface NotificationItem {
  id: string
  type: 'task_completed' | 'task_failed' | 'credit_low' | 'subscription_expiring' | 'system_maintenance'
  title: string
  body: string
  createdAt: number
  read: boolean
}

export interface TaskProgress {
  taskId: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress: number // 0-1
  stage: string
  eta?: number
  result?: unknown
  error?: string
}

const MAX_NOTIFICATIONS = 50

interface RealtimeState {
  wsStatus: WSStatus
  notifications: NotificationItem[]
  taskProgress: Record<string, TaskProgress>

  setWsStatus: (s: WSStatus) => void
  addNotification: (n: NotificationItem) => void
  markAllRead: () => void
  updateTaskProgress: (taskId: string, p: TaskProgress) => void
  removeTaskProgress: (taskId: string) => void
}

export const useRealtimeStore = create<RealtimeState>()(
  persist(
    (set) => ({
      wsStatus: 'idle',
      notifications: [],
      taskProgress: {},

      setWsStatus: (wsStatus) => set({ wsStatus }),

      addNotification: (n) =>
        set((state) => ({
          notifications: [...state.notifications, n].slice(-MAX_NOTIFICATIONS),
        })),

      markAllRead: () =>
        set((state) => ({
          notifications: state.notifications.map((n) => ({ ...n, read: true })),
        })),

      updateTaskProgress: (taskId, p) =>
        set((state) => ({
          taskProgress: { ...state.taskProgress, [taskId]: p },
        })),

      removeTaskProgress: (taskId) =>
        set((state) => {
          const taskProgress = { ...state.taskProgress }
          delete taskProgress[taskId]
          return { taskProgress }
        }),
    }),
    {
      name: 'comicstudio-realtime',
      partialize: (state) => ({ notifications: state.notifications }),
      // taskProgress 不持久化（临时状态）
    }
  )
)
