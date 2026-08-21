import { useState, useRef, useCallback, useEffect } from 'react'
import { fetchSSE } from '@/api/sse'

interface UseSSEReturn {
  data: string
  done: boolean
  error: Error | null
  start: () => void
  abort: () => void
}

/**
 * 发起 SSE 流式请求
 * @param url 请求路径
 * @param body POST body
 */
export function useSSE(url: string, body?: unknown): UseSSEReturn {
  const [data, setData] = useState<string>('')
  const [done, setDone] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const start = useCallback(() => {
    const controller = new AbortController()
    abortRef.current = controller
    setData('')
    setDone(false)
    setError(null)

    fetchSSE({
      url,
      body,
      signal: controller.signal,
      onMessage: (chunk) => setData((prev) => prev + chunk),
      onError: setError,
      onDone: () => setDone(true),
    })
  }, [url, body])

  const abort = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  useEffect(() => () => abort(), [abort])

  return { data, done, error, start, abort }
}
