import http from 'http'
import { BACKEND_URL, BACKEND_HEALTH_ENDPOINT } from '../constants'

/**
 * Check the backend health endpoint.
 * Resolves to true if the backend is reachable and returns 2xx.
 */
export function checkBackendHealth(
  url: string = BACKEND_URL,
  timeoutMs: number = 5000
): Promise<boolean> {
  return new Promise((resolve) => {
    const fullUrl = `${url}${BACKEND_HEALTH_ENDPOINT}`
    let resolved = false

    const timer = setTimeout(() => {
      if (!resolved) {
        resolved = true
        resolve(false)
      }
    }, timeoutMs)

    const req = http.get(fullUrl, (res) => {
      clearTimeout(timer)
      if (resolved) return
      resolved = true
      resolve(res.statusCode !== undefined && res.statusCode >= 200 && res.statusCode < 300)
      res.resume()
    })

    req.on('error', () => {
      clearTimeout(timer)
      if (!resolved) {
        resolved = true
        resolve(false)
      }
    })

    req.on('timeout', () => {
      req.destroy()
      clearTimeout(timer)
      if (!resolved) {
        resolved = true
        resolve(false)
      }
    })
  })
}

/**
 * Wait for the backend to become healthy, polling at a fixed interval.
 * Resolves to true if healthy within the timeout, false otherwise.
 */
export async function waitForBackendHealth(
  url: string = BACKEND_URL,
  timeoutMs: number = 60_000,
  intervalMs: number = 2_000
): Promise<boolean> {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const healthy = await checkBackendHealth(url, 3000)
    if (healthy) return true
    await sleep(intervalMs)
  }
  return false
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
