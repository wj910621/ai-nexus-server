// Shared types used by main, preload, and renderer.

export interface UserInfo {
  username: string
  homedir: string
  platform: NodeJS.Platform
}

export interface FileDialogFilter {
  name: string
  extensions: string[]
}

export interface OpenDialogOptions {
  title?: string
  defaultPath?: string
  filters?: FileDialogFilter[]
  properties?: Array<
    | 'openFile'
    | 'openDirectory'
    | 'multiSelections'
    | 'showHiddenFiles'
    | 'createDirectory'
    | 'promptToCreate'
    | 'noResolveAliases'
    | 'treatPackageAsDirectory'
  >
}

export interface SaveDialogOptions {
  title?: string
  defaultPath?: string
  filters?: FileDialogFilter[]
}

export interface FileReadResult {
  path: string
  content: string
  encoding: string
}

export interface WindowState {
  isMaximized: boolean
  isMinimized: boolean
  isFullScreen: boolean
}

// Shape of the API exposed to the renderer via contextBridge.
export interface ElectronAPI {
  app: {
    getVersion: () => Promise<string>
    getPlatform: () => Promise<NodeJS.Platform>
  }
  window: {
    minimize: () => Promise<void>
    maximize: () => Promise<void>
    unmaximize: () => Promise<void>
    close: () => Promise<void>
    toggleMaximize: () => Promise<void>
    isMaximized: () => Promise<boolean>
    onStateChange: (callback: (state: WindowState) => void) => () => void
  }
  fs: {
    readFile: (path: string, encoding?: string) => Promise<FileReadResult>
    writeFile: (path: string, content: string, encoding?: string) => Promise<void>
    showOpenDialog: (options?: OpenDialogOptions) => Promise<string | null>
    showSaveDialog: (options?: SaveDialogOptions) => Promise<string | null>
    showItemInFolder: (path: string) => Promise<void>
  }
  shell: {
    openExternal: (url: string) => Promise<void>
    openPath: (path: string) => Promise<string>
  }
  clipboard: {
    readText: () => Promise<string>
    writeText: (text: string) => Promise<void>
  }
  system: {
    getUserInfo: () => Promise<UserInfo>
    getPaths: (names: string[]) => Promise<Record<string, string>>
  }
  navigate: {
    onNavigate: (callback: (path: string) => void) => () => void
  }
  updater: {
    check: () => Promise<UpdateCheckResult>
    download: () => Promise<void>
    install: () => Promise<void>
    onStateChange: (callback: (state: UpdaterState) => void) => () => void
  }
  // Frontend integration APIs (added in Task 9)
  memory: {
    append: (sessionId: string, role: string, content: string) => Promise<{ ok: boolean }>
    search: (keyword: string, limit?: number) => Promise<{ records: unknown[]; total: number }>
    recent: (limit?: number) => Promise<{ records: unknown[] }>
  }
  agent: {
    chat: (messages: AgentMessage[], model: string) => Promise<AgentResult>
    createComicScript: (premise?: string, genre?: string) => Promise<AgentResult>
  }
  account: {
    login: (username: string, password: string) => Promise<AccountResult>
    me: () => Promise<AccountResult>
    logout: () => Promise<boolean>
    storyToken: () => Promise<{ ok: boolean; token?: string; code?: string; message?: string }>
  }
  // R3 云服务（模板市场 / 云端资产同步 / 云渲染队列）
  cloud: {
    templates: (genre?: string) => Promise<CloudResult<CloudTemplate[]>>
    listAssets: (kind?: string) => Promise<CloudResult<CloudAsset[]>>
    saveAsset: (asset: CloudAssetInput) => Promise<CloudResult<{ id: number }>>
    deleteAsset: (id: number) => Promise<CloudResult<boolean>>
    enqueueJob: (job: { templateSlug: string; premise?: string; idempotency?: string; shots?: { prompt: string }[] }) => Promise<
      CloudResult<{ jobId: number; duplicate: boolean; shots?: number }>
    >
    listJobs: () => Promise<CloudResult<CloudJob[]>>
    tts: (input: { text: string; voice?: string; speed?: number }) => Promise<CloudResult<TtsAudio>>
  }
  // R4b-1 本机 ComfyUI 渲染通道
  render: {
    comfyProbe: () => Promise<ComfyProbeResult>
    comfyRun: (input: ComfyRenderInput) => Promise<ComfyRenderResult>
  }
  integration: {
    getBackendUrl: () => Promise<string>
    getRuntimeInfo: () => Promise<RuntimeInfo>
    chooseDirectory: () => Promise<string | null>
    saveSettings: (settings: SaveSettingsPayload) => Promise<void>
    completeFirstLaunch: () => Promise<void>
    downloadModel: (name: string) => Promise<void>
    onBackendUrlChange: (callback: (url: string) => void) => () => void
    showNotification: (notification: NotificationPayload) => Promise<void>
  }
}

export interface UpdateCheckResult {
  available: boolean
  currentVersion: string
  latestVersion?: string
  releaseNotes?: string
  releaseUrl?: string
}

// === Frontend integration types ===

/** Runtime info returned by backend `/api/v1/models/runtime`. */
export interface RuntimeInfo {
  deviceType?: 'gpu' | 'cpu' | 'none'
  vramGb?: number
  ramGb?: number
  gpuName?: string
  [key: string]: unknown
}

/** Settings payload persisted via electron-store. */
export interface SaveSettingsPayload {
  dataDir?: string
  telemetry?: boolean
  autoUpdate?: boolean
}

/** Notification payload shown via main-process Notification API. */
export interface NotificationPayload {
  title: string
  body: string
}

export type UpdaterState =
  | { status: 'idle' }
  | { status: 'checking' }
  | { status: 'available'; info: { version: string; releaseNotes?: string } }
  | { status: 'not-available' }
  | { status: 'downloading'; percent: number }
  | { status: 'downloaded' }
  | { status: 'error'; message: string }

// Augment the global Window interface so renderer can access window.electronAPI
declare global {
  interface Window {
    electronAPI: ElectronAPI
  }
}

export {}

// ===== P1 统一主站账号 =====
export interface AccountUser {
  username: string
  email?: string
  credits: number
  role?: string
}

export type AccountErrorCode = 'unauthorized' | 'network' | 'invalid' | 'storage'

export type AccountResult<T = AccountUser | null> =
  | { ok: true; data: T }
  | { ok: false; code: AccountErrorCode; message: string }

// ===== P3 创作智能层（Agent）=====
export interface AgentMessage {
  role: 'system' | 'user' | 'assistant'
  content: string
}

export type AgentResult =
  | { ok: true; content: string; model: string }
  | { ok: false; code: 'unauthorized' | 'network' | 'invalid' | 'quota'; message: string }

// ===== R3 云服务（与 server/comic_cloud.js 契约一致）=====
export interface CloudTemplate {
  id: number
  slug: string
  title: string
  genre: string
  description: string
  price_credits: number
  shots: number
  author?: string
}

export interface CloudAsset {
  id: number
  kind: string
  title: string
  genre: string
  premise: string
  content: string
  created_at: number
  updated_at: number
}

export interface CloudAssetInput {
  kind?: string
  title?: string
  genre?: string
  premise?: string
  content: string
}

export interface CloudJob {
  id: number
  template_slug: string
  template_title: string
  genre: string
  premise: string
  status: 'queued' | 'rendering' | 'done' | 'failed'
  asset_id?: number | null
  error?: string | null
  created_at: number
  updated_at: number
}

export type CloudErrorCode = 'unauthorized' | 'network' | 'invalid'

export type CloudResult<T> = { ok: true; data: T } | { ok: false; code: CloudErrorCode; message: string }

// ===== R4b-1 本机 ComfyUI 渲染通道 =====
export interface ComfyDevice {
  name: string
  vramTotalMB: number
  vramFreeMB: number
}

export interface ComfyProbeResult {
  available: boolean
  base: string
  version?: string
  devices: ComfyDevice[]
  checkpoints: string[]
  message?: string
}

export interface ComfyRenderInput {
  prompt: string
  negative?: string
  width?: number
  height?: number
  steps?: number
  cfg?: number
  seed?: number
  ckpt?: string
  timeoutMs?: number
}

export interface ComfyImage {
  filename: string
  subfolder: string
  type: string
  filePath?: string
  dataUrl?: string
}

export type ComfyErrorCode = 'offline' | 'no-model' | 'timeout' | 'invalid' | 'network'

export type ComfyRenderResult =
  | { ok: true; promptId: string; elapsedMs: number; images: ComfyImage[] }
  | { ok: false; code: ComfyErrorCode; message: string }

// ===== R4b-3 语音合成（TTS）=====
export interface TtsAudio {
  format: string
  bytes: number
  /** mp3 原始 base64（服务端返回） */
  audioBase64: string
  model: string
  voice: string
  chars: number
  /** 主进程落盘路径（userData/audio/） */
  filePath?: string
  /** 可直接播放的 data URL */
  dataUrl?: string
}
