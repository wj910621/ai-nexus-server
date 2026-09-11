import { ipcRenderer } from 'electron'
import { IPC_CHANNELS } from '@shared/ipc-channels'
import type { ElectronAPI } from '@shared/types'

/**
 * The actual implementation of the ElectronAPI surface, using ipcRenderer.
 * Exposed to renderer via contextBridge in preload/index.ts.
 */
export const api: ElectronAPI = {
  app: {
    getVersion: () => ipcRenderer.invoke(IPC_CHANNELS.APP_GET_VERSION),
    getPlatform: () => ipcRenderer.invoke(IPC_CHANNELS.APP_GET_PLATFORM),
  },
  window: {
    minimize: () => ipcRenderer.invoke(IPC_CHANNELS.WINDOW_MINIMIZE),
    maximize: () => ipcRenderer.invoke(IPC_CHANNELS.WINDOW_MAXIMIZE),
    unmaximize: () => ipcRenderer.invoke(IPC_CHANNELS.WINDOW_UNMAXIMIZE),
    close: () => ipcRenderer.invoke(IPC_CHANNELS.WINDOW_CLOSE),
    toggleMaximize: () => ipcRenderer.invoke(IPC_CHANNELS.WINDOW_TOGGLE_MAXIMIZE),
    isMaximized: () => ipcRenderer.invoke(IPC_CHANNELS.WINDOW_IS_MAXIMIZED),
    onStateChange: (callback) => {
      const handler = (_event: unknown, state: any) => callback(state)
      ipcRenderer.on(IPC_CHANNELS.WINDOW_STATE_CHANGE, handler)
      return () => {
        ipcRenderer.removeListener(IPC_CHANNELS.WINDOW_STATE_CHANGE, handler)
      }
    },
  },
  fs: {
    readFile: (path, encoding = 'utf-8') =>
      ipcRenderer.invoke(IPC_CHANNELS.FS_READ_FILE, { path, encoding }),
    writeFile: (path, content, encoding = 'utf-8') =>
      ipcRenderer.invoke(IPC_CHANNELS.FS_WRITE_FILE, { path, content, encoding }),
    showOpenDialog: (options) =>
      ipcRenderer.invoke(IPC_CHANNELS.FS_SHOW_OPEN_DIALOG, options || {}),
    showSaveDialog: (options) =>
      ipcRenderer.invoke(IPC_CHANNELS.FS_SHOW_SAVE_DIALOG, options || {}),
    showItemInFolder: (path) =>
      ipcRenderer.invoke(IPC_CHANNELS.FS_SHOW_ITEM_IN_FOLDER, path),
  },
  shell: {
    openExternal: (url) => ipcRenderer.invoke(IPC_CHANNELS.SHELL_OPEN_EXTERNAL, url),
    openPath: (path) => ipcRenderer.invoke(IPC_CHANNELS.SHELL_OPEN_PATH, path),
  },
  clipboard: {
    readText: () => ipcRenderer.invoke(IPC_CHANNELS.CLIPBOARD_READ_TEXT),
    writeText: (text) => ipcRenderer.invoke(IPC_CHANNELS.CLIPBOARD_WRITE_TEXT, text),
  },
  system: {
    getUserInfo: () => ipcRenderer.invoke(IPC_CHANNELS.SYSTEM_GET_USER_INFO),
    getPaths: (names) => ipcRenderer.invoke(IPC_CHANNELS.SYSTEM_GET_PATHS, names),
  },
  navigate: {
    onNavigate: (callback) => {
      const handler = (_event: unknown, path: string) => callback(path)
      ipcRenderer.on(IPC_CHANNELS.NAVIGATE, handler)
      return () => {
        ipcRenderer.removeListener(IPC_CHANNELS.NAVIGATE, handler)
      }
    },
  },
  updater: {
    check: () => ipcRenderer.invoke(IPC_CHANNELS.UPDATER_CHECK),
    download: () => ipcRenderer.invoke(IPC_CHANNELS.UPDATER_DOWNLOAD),
    install: () => ipcRenderer.invoke(IPC_CHANNELS.UPDATER_INSTALL),
    onStateChange: (callback) => {
      const handler = (_event: unknown, state: any) => callback(state)
      ipcRenderer.on(IPC_CHANNELS.UPDATER_STATE_CHANGE, handler)
      return () => {
        ipcRenderer.removeListener(IPC_CHANNELS.UPDATER_STATE_CHANGE, handler)
      }
    },
  },

  // P1: 统一主站账号(login/me/logout), 由主进程 account IPC 实现
  account: {
    login: (username: string, password: string) => ipcRenderer.invoke(IPC_CHANNELS.ACCOUNT_LOGIN, { username, password }),
    me: () => ipcRenderer.invoke(IPC_CHANNELS.ACCOUNT_ME),
    logout: () => ipcRenderer.invoke(IPC_CHANNELS.ACCOUNT_LOGOUT),
    storyToken: () => ipcRenderer.invoke(IPC_CHANNELS.ACCOUNT_STORY_TOKEN),
  },
  // R2: 记忆系统(跨会话记忆搜索)
  memory: {
    append: (sessionId, role, content) => ipcRenderer.invoke(IPC_CHANNELS.MEMORY_APPEND, { sessionId, role, content }),
    search: (keyword, limit) => ipcRenderer.invoke(IPC_CHANNELS.MEMORY_SEARCH, { keyword, limit }),
    recent: (limit) => ipcRenderer.invoke(IPC_CHANNELS.MEMORY_RECENT, { limit }),
  },
  // R3: 云服务(模板市场/云资产同步/云渲染队列)
  cloud: {
    templates: (genre?: string) => ipcRenderer.invoke(IPC_CHANNELS.CLOUD_TEMPLATES, { genre }),
    listAssets: (kind?: string) => ipcRenderer.invoke(IPC_CHANNELS.CLOUD_ASSET_LIST, { kind }),
    saveAsset: (asset) => ipcRenderer.invoke(IPC_CHANNELS.CLOUD_ASSET_SAVE, asset),
    deleteAsset: (id: number) => ipcRenderer.invoke(IPC_CHANNELS.CLOUD_ASSET_DELETE, { id }),
    enqueueJob: (job) => ipcRenderer.invoke(IPC_CHANNELS.CLOUD_JOB_ENQUEUE, job),
    listJobs: () => ipcRenderer.invoke(IPC_CHANNELS.CLOUD_JOB_LIST),
  },
  // P3: 创作智能层 Agent（对话/漫剧脚本生成）
  agent: {
    chat: (messages, model) => ipcRenderer.invoke(IPC_CHANNELS.AGENT_CHAT, { messages, model }),
    createComicScript: (premise, genre) => ipcRenderer.invoke(IPC_CHANNELS.AGENT_COMIC_SCRIPT, { premise, genre }),
  },
  // Frontend integration APIs (added in Task 9).
  // Implementation defers to main-process IPC handlers to keep preload
  // free of main-only modules (e.g. BrowserWindow, dialog direct usage).
  integration: {
    getBackendUrl: () => ipcRenderer.invoke(IPC_CHANNELS.BACKEND_GET_URL),
    getRuntimeInfo: () => ipcRenderer.invoke(IPC_CHANNELS.BACKEND_GET_RUNTIME),
    chooseDirectory: () => ipcRenderer.invoke(IPC_CHANNELS.DIALOG_CHOOSE_DIRECTORY),
    saveSettings: (settings) =>
      ipcRenderer.invoke(IPC_CHANNELS.SETTINGS_SAVE, settings),
    completeFirstLaunch: () => ipcRenderer.invoke(IPC_CHANNELS.FIRST_LAUNCH_COMPLETE),
    downloadModel: (name) => ipcRenderer.invoke(IPC_CHANNELS.MODEL_DOWNLOAD, name),
    onBackendUrlChange: (callback) => {
      const handler = (_event: unknown, url: string) => callback(url)
      ipcRenderer.on(IPC_CHANNELS.BACKEND_URL_CHANGED, handler)
      return () => {
        ipcRenderer.removeListener(IPC_CHANNELS.BACKEND_URL_CHANGED, handler)
      }
    },
    showNotification: (notification) =>
      ipcRenderer.invoke(IPC_CHANNELS.NOTIFICATION_SHOW, notification),
  },
}
