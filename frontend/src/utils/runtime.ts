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
      // P2 统一主站账号桥（desktop preload account IPC）
      account?: {
        login: (username: string, password: string) => Promise<unknown>
        me: () => Promise<unknown>
        logout: () => Promise<boolean>
        storyToken?: () => Promise<{ ok?: boolean; token?: string; code?: string; message?: string }>
      }
      agent?: {
        chat: (messages: unknown[], model: string) => Promise<unknown>
        createComicScript: (premise?: string, genre?: string) => Promise<unknown>
      }
      // R2 记忆系统（跨会话检索）
      memory?: {
        append: (sessionId: string, role: string, content: string) => Promise<{ ok: boolean }>
        search: (keyword: string, limit?: number) => Promise<{ records: MemoryRecord[]; total: number }>
        recent: (limit?: number) => Promise<{ records: MemoryRecord[] }>
      }
      // R3 云服务（模板市场 / 云端资产同步 / 云渲染队列）
      cloud?: {
        templates: (genre?: string) => Promise<unknown>
        listAssets: (kind?: string) => Promise<unknown>
        saveAsset: (asset: unknown) => Promise<unknown>
        deleteAsset: (id: number) => Promise<unknown>
        enqueueJob: (job: unknown) => Promise<unknown>
        listJobs: () => Promise<unknown>
        tts?: (input: unknown) => Promise<unknown>
      }
      // R4b-1 本机 ComfyUI 渲染通道
      render?: {
        comfyProbe: () => Promise<unknown>
        comfyRun: (input: unknown) => Promise<unknown>
      }
    }
  }
}

/** R2 记忆记录（与 desktop MemoryService 输出一致） */
export interface MemoryRecord {
  ts?: number
  username?: string
  sessionId?: string
  role?: string
  content?: string
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
