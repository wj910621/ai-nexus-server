import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useWebSocket } from '@/hooks/useWebSocket'
import { wsClient, WSMessage } from '@/api/websocket'

vi.mock('@/utils/token', () => ({
  tokenStorage: {
    getAccessToken: () => 'mock-token',
  },
}))

describe('useWebSocket', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(wsClient, 'getStatus').mockReturnValue('connected')
    vi.spyOn(wsClient, 'connect').mockResolvedValue(undefined)
  })

  it('channel 为 null 时不订阅', () => {
    const { result } = renderHook(() => useWebSocket(null))
    expect(result.current).toBeNull()
  })

  it('订阅后收到消息应更新 state', () => {
    let capturedHandler: ((msg: WSMessage) => void) | null = null
    vi.spyOn(wsClient, 'subscribe').mockImplementation((channel, handler) => {
      capturedHandler = handler
      return () => {}
    })

    const { result } = renderHook(() => useWebSocket('task:123'))

    expect(result.current).toBeNull()

    act(() => {
      capturedHandler?.({ type: 'progress', channel: 'task:123', data: { progress: 0.5 } })
    })

    expect(result.current).toEqual({
      type: 'progress',
      channel: 'task:123',
      data: { progress: 0.5 },
    })
  })

  it('unmount 应取消订阅', () => {
    const unsubscribe = vi.fn()
    vi.spyOn(wsClient, 'subscribe').mockReturnValue(unsubscribe)

    const { unmount } = renderHook(() => useWebSocket('task:456'))

    unmount()

    expect(unsubscribe).toHaveBeenCalled()
  })

  it('channel 变化应重新订阅', () => {
    const subscribe = vi.spyOn(wsClient, 'subscribe').mockReturnValue(() => {})

    const { rerender } = renderHook(({ channel }) => useWebSocket(channel), {
      initialProps: { channel: 'task:1' },
    })

    rerender({ channel: 'task:2' })

    expect(subscribe).toHaveBeenCalledWith('task:1', expect.any(Function))
    expect(subscribe).toHaveBeenCalledWith('task:2', expect.any(Function))
  })
})
