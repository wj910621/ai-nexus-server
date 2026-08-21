import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

describe('runtime utils', () => {
  beforeEach(() => {
    delete (window as any).electronAPI
    vi.resetModules()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('isElectron 应为 false（无 electronAPI）', async () => {
    const { isElectron } = await import('@/utils/runtime')
    expect(isElectron).toBe(false)
  })

  it('isElectron 应为 true（有 electronAPI）', async () => {
    ;(window as any).electronAPI = { getBackendUrl: () => 'http://127.0.0.1:8000' }
    const { isElectron } = await import('@/utils/runtime')
    expect(isElectron).toBe(true)
  })

  it('getBackendUrl 默认返回空字符串', async () => {
    const { getBackendUrl } = await import('@/utils/runtime')
    expect(getBackendUrl()).toBe('')
  })

  it('getBackendUrl 返回 electronAPI 提供的 URL', async () => {
    ;(window as any).electronAPI = { getBackendUrl: () => 'http://127.0.0.1:8000' }
    const { getBackendUrl } = await import('@/utils/runtime')
    expect(getBackendUrl()).toBe('http://127.0.0.1:8000')
  })

  it('getWebSocketUrl uses the same-origin endpoint in web mode', async () => {
    const { getWebSocketUrl } = await import('@/utils/runtime')
    const url = new URL(getWebSocketUrl('token with spaces'))
    expect(url.protocol).toBe('ws:')
    expect(url.pathname).toBe('/ws')
    expect(url.searchParams.get('token')).toBe('token with spaces')
  })

  it('getWebSocketUrl uses the desktop backend in Electron mode', async () => {
    ;(window as any).electronAPI = { getBackendUrl: () => 'https://127.0.0.1:8000' }
    const { getWebSocketUrl } = await import('@/utils/runtime')
    const url = new URL(getWebSocketUrl('desktop-token'))
    expect(url.origin).toBe('wss://127.0.0.1:8000')
    expect(url.pathname).toBe('/ws')
    expect(url.searchParams.get('token')).toBe('desktop-token')
  })
})
