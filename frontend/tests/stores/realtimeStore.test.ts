import { describe, it, expect, beforeEach } from 'vitest'
import { useRealtimeStore, NotificationItem } from '@/stores/realtimeStore'

describe('realtimeStore', () => {
  beforeEach(() => {
    useRealtimeStore.setState({
      wsStatus: 'idle',
      notifications: [],
      taskProgress: {},
    })
  })

  it('addNotification 应追加到末尾（FIFO）', () => {
    const n1: NotificationItem = {
      id: '1', type: 'task_completed', title: 't1', body: 'b1', createdAt: 1, read: false,
    }
    const n2: NotificationItem = {
      id: '2', type: 'task_failed', title: 't2', body: 'b2', createdAt: 2, read: false,
    }
    
    useRealtimeStore.getState().addNotification(n1)
    useRealtimeStore.getState().addNotification(n2)
    
    const state = useRealtimeStore.getState()
    expect(state.notifications).toHaveLength(2)
    expect(state.notifications[0].id).toBe('1')
    expect(state.notifications[1].id).toBe('2')
  })

  it('notifications 超过 50 条应裁剪', () => {
    for (let i = 0; i < 55; i++) {
      useRealtimeStore.getState().addNotification({
        id: `${i}`, type: 'task_completed', title: `t${i}`, body: 'b', createdAt: i, read: false,
      })
    }
    
    const state = useRealtimeStore.getState()
    expect(state.notifications).toHaveLength(50)
    // 保留最后 50 条（5-54）
    expect(state.notifications[0].id).toBe('5')
    expect(state.notifications[49].id).toBe('54')
  })

  it('markAllRead 应将所有通知标记为已读', () => {
    useRealtimeStore.getState().addNotification({
      id: '1', type: 'task_completed', title: 't', body: 'b', createdAt: 1, read: false,
    })
    
    useRealtimeStore.getState().markAllRead()
    
    expect(useRealtimeStore.getState().notifications[0].read).toBe(true)
  })

  it('updateTaskProgress 应更新指定 taskId', () => {
    useRealtimeStore.getState().updateTaskProgress('task-1', {
      taskId: 'task-1', status: 'running', progress: 0.5, stage: 'generating',
    })
    
    const state = useRealtimeStore.getState()
    expect(state.taskProgress['task-1']).toEqual({
      taskId: 'task-1', status: 'running', progress: 0.5, stage: 'generating',
    })
  })

  it('removeTaskProgress 应移除指定 taskId', () => {
    useRealtimeStore.getState().updateTaskProgress('task-1', {
      taskId: 'task-1', status: 'completed', progress: 1, stage: 'done',
    })
    useRealtimeStore.getState().removeTaskProgress('task-1')
    
    expect(useRealtimeStore.getState().taskProgress['task-1']).toBeUndefined()
  })

  it('setWsStatus 应更新状态', () => {
    useRealtimeStore.getState().setWsStatus('connected')
    expect(useRealtimeStore.getState().wsStatus).toBe('connected')
  })
})
