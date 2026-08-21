import { describe, it, expect, beforeEach, vi } from 'vitest'
import { fetchSSE } from '@/api/sse'

// Mock fetch
function createMockResponse(chunks: string[]): Response {
  const encoder = new TextEncoder()
  const stream = new ReadableStream({
    start(controller) {
      chunks.forEach(chunk => controller.enqueue(encoder.encode(chunk)))
      controller.close()
    },
  })
  return new Response(stream, { status: 200 })
}

vi.mock('@/utils/token', () => ({
  tokenStorage: {
    getAccessToken: () => 'mock-token',
  },
}))

global.fetch = vi.fn()

describe('fetchSSE', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('正常流式接收 data 事件', async () => {
    const chunks = [
      'data: {"type":"token","content":"好"}\n\n',
      'data: {"type":"token","content":"的"}\n\n',
    ]
    ;(global.fetch as any).mockResolvedValue(createMockResponse(chunks))
    
    const messages: string[] = []
    await fetchSSE({
      url: '/api/v1/chat',
      onMessage: (data) => messages.push(data),
    })
    
    expect(messages).toEqual([
      '{"type":"token","content":"好"}',
      '{"type":"token","content":"的"}',
    ])
  })

  it('HTTP 错误应调用 onError', async () => {
    ;(global.fetch as any).mockResolvedValue(new Response('Server Error', { status: 500 }))
    
    const onError = vi.fn()
    await fetchSSE({
      url: '/api/v1/chat',
      onMessage: () => {},
      onError,
    })
    
    expect(onError).toHaveBeenCalledWith(expect.any(Error))
  })

  it('AbortSignal 中断应调用 onError', async () => {
    const controller = new AbortController()
    controller.abort()
    ;(global.fetch as any).mockRejectedValue(
      Object.assign(new Error('aborted'), { name: 'AbortError' })
    )
    
    const onError = vi.fn()
    await fetchSSE({
      url: '/api/v1/chat',
      signal: controller.signal,
      onMessage: () => {},
      onError,
    })
    
    expect(onError).toHaveBeenCalledWith(expect.any(Error))
  })

  it('请求应包含 Authorization header', async () => {
    ;(global.fetch as any).mockResolvedValue(createMockResponse([]))
    
    await fetchSSE({
      url: '/api/v1/chat',
      onMessage: () => {},
    })
    
    expect(global.fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer mock-token',
        }),
      })
    )
  })

  it('空响应体应调用 onError', async () => {
    ;(global.fetch as any).mockResolvedValue(new Response(null, { status: 200 }))
    
    const onError = vi.fn()
    await fetchSSE({
      url: '/api/v1/chat',
      onMessage: () => {},
      onError,
    })
    
    expect(onError).toHaveBeenCalledWith(expect.any(Error))
  })

  it('正常结束应调用 onDone', async () => {
    ;(global.fetch as any).mockResolvedValue(createMockResponse([]))
    
    const onDone = vi.fn()
    await fetchSSE({
      url: '/api/v1/chat',
      onMessage: () => {},
      onDone,
    })
    
    expect(onDone).toHaveBeenCalled()
  })
})
