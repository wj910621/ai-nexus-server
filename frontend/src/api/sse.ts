import { getApiUrl } from '@/utils/runtime'
import { tokenStorage } from '@/utils/token'

export interface SSEOptions {
  url: string
  body?: unknown
  signal?: AbortSignal
  onMessage: (data: string) => void
  onError?: (err: Error) => void
  onDone?: () => void
}

const SSE_TIMEOUT = 60000

/**
 * 基于 fetch + ReadableStream 的 SSE 客户端
 * 不使用 EventSource（不支持自定义 header 和 POST）
 */
export async function fetchSSE(options: SSEOptions): Promise<void> {
  const { url, body, signal, onMessage, onError, onDone } = options

  const fullUrl = getApiUrl(url)
  const token = tokenStorage.getAccessToken()

  // 超时控制
  const timeoutController = new AbortController()
  const timeoutId = setTimeout(() => {
    timeoutController.abort()
  }, SSE_TIMEOUT)

  // 合并外部 signal 和超时 signal
  const combinedSignal = signal
    ? AbortSignal.any([signal, timeoutController.signal])
    : timeoutController.signal

  try {
    const response = await fetch(fullUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
      signal: combinedSignal,
    })

    if (!response.ok) {
      const err = new Error(`HTTP ${response.status}`)
      onError?.(err)
      return
    }

    if (!response.body) {
      onError?.(new Error('No response body'))
      return
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let lastDataTime = Date.now()

    // 重置超时计时器（每次收到数据时）
    const dataTimeoutController = new AbortController()
    const dataTimeoutId = setInterval(() => {
      if (Date.now() - lastDataTime > SSE_TIMEOUT) {
        dataTimeoutController.abort()
        clearInterval(dataTimeoutId)
      }
    }, 1000)

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        lastDataTime = Date.now()
        buffer += decoder.decode(value, { stream: true })
        const events = buffer.split('\n\n')
        buffer = events.pop() || ''

        for (const event of events) {
          if (event.startsWith('data: ')) {
            onMessage(event.slice(6))
          }
        }
      }
      onDone?.()
    } finally {
      clearInterval(dataTimeoutId)
      clearTimeout(timeoutId)
    }
  } catch (err) {
    clearTimeout(timeoutId)
    if ((err as Error).name === 'AbortError') {
      onError?.(new Error('SSE aborted'))
    } else {
      onError?.(err as Error)
    }
  }
}
