import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useTaskProgress } from '@/hooks/useTaskProgress'
import { useRealtimeStore, TaskProgress } from '@/stores/realtimeStore'

// Mock useWebSocket
let mockLastMessage: any = null
vi.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: () => mockLastMessage,
}))

describe('useTaskProgress', () => {
  beforeEach(() => {
    mockLastMessage = null
    useRealtimeStore.setState({ taskProgress: {} })
  })

  it('收到 progress 消息应更新 store', () => {
    const { rerender } = renderHook(() => useTaskProgress('task-1'))

    mockLastMessage = {
      type: 'progress',
      channel: 'task:task-1',
      data: {
        taskId: 'task-1',
        status: 'running',
        progress: 0.6,
        stage: 'generating',
      } as TaskProgress,
    }

    rerender()

    expect(useRealtimeStore.getState().taskProgress['task-1']).toEqual({
      taskId: 'task-1',
      status: 'running',
      progress: 0.6,
      stage: 'generating',
    })
  })

  it('taskId 为 null 应返回 undefined', () => {
    const { result } = renderHook(() => useTaskProgress(null))
    expect(result.current).toBeUndefined()
  })

  it('应返回 store 中的进度', () => {
    useRealtimeStore.setState({
      taskProgress: {
        'task-2': {
          taskId: 'task-2',
          status: 'running',
          progress: 0.3,
          stage: 'init',
        },
      },
    })

    const { result } = renderHook(() => useTaskProgress('task-2'))

    expect(result.current).toEqual({
      taskId: 'task-2',
      status: 'running',
      progress: 0.3,
      stage: 'init',
    })
  })
})
