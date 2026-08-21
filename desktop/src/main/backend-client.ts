// Thin HTTP client for calling the backend API from the Electron main process.
// Centralizes URL resolution, auth token injection, and error handling so
// first-launch wizard and other main-process features share one entry point.

import { BACKEND_URL } from './constants'

export interface BackendClientOptions {
  /** Override base URL (testing). */
  baseUrl?: string
  /** Optional bearer token. */
  token?: string
  /** Default request timeout in ms. */
  timeoutMs?: number
}

export class BackendClient {
  private readonly baseUrl: string
  private readonly token?: string
  private readonly timeoutMs: number

  constructor(opts: BackendClientOptions = {}) {
    this.baseUrl = (opts.baseUrl || BACKEND_URL).replace(/\/$/, '')
    this.token = opts.token
    this.timeoutMs = opts.timeoutMs ?? 30_000
  }

  async get<T = unknown>(path: string): Promise<T> {
    return this.request<T>('GET', path)
  }

  async post<T = unknown>(path: string, body?: unknown): Promise<T> {
    return this.request<T>('POST', path, body)
  }

  async delete<T = unknown>(path: string): Promise<T> {
    return this.request<T>('DELETE', path)
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
  ): Promise<T> {
    const url = `${this.baseUrl}${path.startsWith('/') ? path : `/${path}`}`
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), this.timeoutMs)

    const headers: Record<string, string> = {
      Accept: 'application/json',
    }
    if (body !== undefined) {
      headers['Content-Type'] = 'application/json'
    }
    if (this.token) {
      headers.Authorization = `Bearer ${this.token}`
    }

    try {
      const resp = await fetch(url, {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      })
      if (!resp.ok) {
        const text = await resp.text().catch(() => '')
        throw new BackendClientError(
          `HTTP ${resp.status}: ${text || resp.statusText}`,
          resp.status,
        )
      }
      const ct = resp.headers.get('content-type') || ''
      if (ct.includes('application/json')) {
        return (await resp.json()) as T
      }
      return (await resp.text()) as unknown as T
    } finally {
      clearTimeout(timer)
    }
  }
}

export class BackendClientError extends Error {
  constructor(message: string, public statusCode: number) {
    super(message)
    this.name = 'BackendClientError'
  }
}

// Shared singleton used by first-launch wizard and other main-process callers.
export const backendClient = new BackendClient()
