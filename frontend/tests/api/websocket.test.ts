import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { wsClient, WSStatus } from '@/api/websocket'

// Mock WebSocket
class MockWebSocket {
  static instances: MockWebSocket[] = []
  static CONNECTING = 0
  static OPEN = 1
  static CLOSING = 2
  static CLOSED = 3
  onopen: (() => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onclose: ((event: { code: number }) => void) | null = null
  onerror: (() => void) | null = null
  readyState = 0
  sentMessages: string[] = []

  constructor(public url: string) {
    MockWebSocket.instances.push(this)
    setTimeout(() => {
      this.readyState = 1
      this.onopen?.()
    }, 0)
  }

  send(data: string) {
    this.sentMessages.push(data)
  }

  close() {
    this.readyState = 3
  }

  simulateMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) })
  }
}

vi.stubGlobal('WebSocket', MockWebSocket)

describe('WebSocketClient', () => {
  beforeEach(() => {
    MockWebSocket.instances = []
  })

  afterEach(async () => {
    await wsClient.disconnect()
  })

  it('connect 后状态应为 connected', async () => {
    await wsClient.connect('test-token')
    expect(wsClient.getStatus()).toBe('connected')
  })

  it('subscribe 应发送 subscribe 消息', async () => {
    await wsClient.connect('test-token')
    const mock = MockWebSocket.instances[0]
    
    wsClient.subscribe('task:123', () => {})
    
    expect(mock.sentMessages).toContain(
      JSON.stringify({ type: 'subscribe', channel: 'task:123' })
    )
  })

  it('多次 subscribe 同一频道应只发送一次 subscribe', async () => {
    await wsClient.connect('test-token')
    const mock = MockWebSocket.instances[0]
    
    const unsub1 = wsClient.subscribe('task:123', () => {})
    const unsub2 = wsClient.subscribe('task:123', () => {})
    
    const subscribeCount = mock.sentMessages.filter(
      m => m === JSON.stringify({ type: 'subscribe', channel: 'task:123' })
    ).length
    expect(subscribeCount).toBe(1)
    
    unsub1()
    unsub2()
  })

  it('所有 handler 取消订阅后应发送 unsubscribe', async () => {
    await wsClient.connect('test-token')
    const mock = MockWebSocket.instances[0]
    
    const unsub1 = wsClient.subscribe('task:456', () => {})
    const unsub2 = wsClient.subscribe('task:456', () => {})
    
    unsub1()
    expect(mock.sentMessages).not.toContain(
      JSON.stringify({ type: 'unsubscribe', channel: 'task:456' })
    )
    
    unsub2()
    expect(mock.sentMessages).toContain(
      JSON.stringify({ type: 'unsubscribe', channel: 'task:456' })
    )
  })

  it('收到 channel 消息应调用对应 handler', async () => {
    await wsClient.connect('test-token')
    const mock = MockWebSocket.instances[0]
    
    const handler = vi.fn()
    wsClient.subscribe('task:789', handler)
    
    mock.simulateMessage({ type: 'progress', channel: 'task:789', data: { progress: 0.5 } })
    
    expect(handler).toHaveBeenCalledWith({
      type: 'progress',
      channel: 'task:789',
      data: { progress: 0.5 },
    })
  })

  it('pong 消息不应转发给 handler', async () => {
    await wsClient.connect('test-token')
    const mock = MockWebSocket.instances[0]
    
    const handler = vi.fn()
    wsClient.subscribe('task:999', handler)
    
    mock.simulateMessage({ type: 'pong' })
    
    expect(handler).not.toHaveBeenCalled()
  })

  it('onStatusChange 应被通知', async () => {
    const listener = vi.fn()
    wsClient.onStatusChange(listener)
    
    await wsClient.connect('test-token')
    
    expect(listener).toHaveBeenCalledWith('connecting')
    expect(listener).toHaveBeenCalledWith('connected')
  })

  it('认证失败（4001）应标记 closed 且不重连', async () => {
    await wsClient.connect('test-token')
    const mock = MockWebSocket.instances[0]
    
    mock.onclose?.({ code: 4001 })
    
    expect(wsClient.getStatus()).toBe('closed')
  })
})
