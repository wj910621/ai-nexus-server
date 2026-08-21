import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useWorkflowStream } from '@/hooks/useWorkflowStream'

let mockLastMessage: any = null
vi.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: () => mockLastMessage,
}))

describe('useWorkflowStream', () => {
  beforeEach(() => {
    mockLastMessage = null
  })

  it('node_start 应将节点标记为 running', () => {
    const { rerender, result } = renderHook(() => useWorkflowStream('exec-1'))

    mockLastMessage = { type: 'node_start', node_id: 'node_1' }
    rerender()

    expect(result.current.nodes['node_1'].status).toBe('running')
    expect(result.current.status).toBe('running')
  })

  it('node_complete 应将节点标记为 completed', () => {
    const { rerender, result } = renderHook(() => useWorkflowStream('exec-2'))

    mockLastMessage = { type: 'node_start', node_id: 'node_1' }
    rerender()
    mockLastMessage = { type: 'node_complete', node_id: 'node_1', result: 'ok', duration_ms: 1000 }
    rerender()

    expect(result.current.nodes['node_1'].status).toBe('completed')
    expect(result.current.nodes['node_1'].durationMs).toBe(1000)
  })

  it('execution_complete 应更新整体状态', () => {
    const { rerender, result } = renderHook(() => useWorkflowStream('exec-3'))

    mockLastMessage = { type: 'execution_complete', status: 'success', total_duration_ms: 5000 }
    rerender()

    expect(result.current.status).toBe('success')
    expect(result.current.totalDurationMs).toBe(5000)
  })
})
