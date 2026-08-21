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
