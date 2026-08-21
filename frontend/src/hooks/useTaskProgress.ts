import { useEffect } from 'react'
import { useWebSocket } from './useWebSocket'
import { useRealtimeStore, TaskProgress } from '@/stores/realtimeStore'

/**
 * 订阅任务进度
 * @param taskId 任务 ID；传 null 不订阅
 */
export function useTaskProgress(taskId: string | null): TaskProgress | undefined {
  const lastMsg = useWebSocket(taskId ? `task:${taskId}` : null)
  const removeTaskProgress = useRealtimeStore((s) => s.removeTaskProgress)

  useEffect(() => {
    if (!lastMsg || !taskId) return

    if (lastMsg.type === 'progress' && lastMsg.data) {
      useRealtimeStore.getState().updateTaskProgress(taskId, lastMsg.data as TaskProgress)
    }
  }, [lastMsg, taskId])

  // 任务完成后 3s 自动清理
  useEffect(() => {
    if (!taskId) return
    const progress = useRealtimeStore.getState().taskProgress[taskId]
    if (progress && (progress.status === 'completed' || progress.status === 'failed' || progress.status === 'cancelled')) {
      const timer = setTimeout(() => {
        removeTaskProgress(taskId)
      }, 3000)
      return () => clearTimeout(timer)
    }
  }, [lastMsg, taskId, removeTaskProgress])

  return useRealtimeStore((s) => (taskId ? s.taskProgress[taskId] : undefined))
}
