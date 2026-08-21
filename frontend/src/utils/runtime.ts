/**
 * 运行时环境检测与抽象
 * Web 端 fallback 到浏览器默认行为
 * Desktop 端通过 preload bridge 调用 Electron 主进程
 */

declare global {
  interface Window {
    electronAPI?: {
      getBackendUrl?: () => string
      getRuntimeInfo?: () => Promise<RuntimeInfo>
      chooseDirectory?: () => Promise<string | null>
      saveSettings?: (s: unknown) => Promise<void>
      completeFirstLaunch?: () => Promise<void>
      downloadModel?: (name: string) => Promise<void>
      onBackendUrlChange?: (cb: (url: string) => void) => () => void
      showNotification?: (n: unknown) => void
    }
  }
}

export interface RuntimeInfo {
  hasGpu: boolean
  gpuName: string
  vramMB: number
  ramMB: number
  recommendedProvider: 'local-gpu' | 'local-cpu' | 'remote'
  platform: string
}

export const isElectron: boolean =
  typeof window !== 'undefined' && 'electronAPI' in window

/**
 * 获取后端 URL
 * - Web 端：返回空字符串（使用同源相对路径）
 * - Desktop 端：返回 http://127.0.0.1:{port}
 */
export function getBackendUrl(): string {
  return window.electronAPI?.getBackendUrl?.() ?? ''
}

/**
 * 获取 WebSocket URL
 */
export function getWebSocketUrl(token: string): string {
  const baseUrl = getBackendUrl()
  if (baseUrl) {
    return `${baseUrl.replace(/^http/, 'ws')}/ws?token=${encodeURIComponent(token)}`
  }

  const configuredPath = import.meta.env.VITE_WS_BASE_URL || '/ws'
  const configuredUrl = new URL(configuredPath, window.location.origin)
  configuredUrl.protocol = configuredUrl.protocol.replace(/^http/, 'ws')
  configuredUrl.searchParams.set('token', token)
  return configuredUrl.toString()
}

/**
 * 获取 SSE/API URL（拼接相对路径）
 */
export function getApiUrl(path: string): string {
  const backendUrl = getBackendUrl()
  if (backendUrl) {
    return `${backendUrl}${path}`
  }

  const configuredBase = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')
  const normalizedPath = path.startsWith('/api/') ? path.slice(4) : path
  return `${configuredBase}${normalizedPath.startsWith('/') ? normalizedPath : `/${normalizedPath}`}`
}
