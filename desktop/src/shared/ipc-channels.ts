// Centralized IPC channel name constants.
// All channels are prefixed with the app namespace to avoid collisions.
import { IPC_PREFIX } from '@main/constants'

export const IPC_CHANNELS = {
  // App info
  APP_GET_VERSION: `${IPC_PREFIX}app:getVersion`,
  APP_GET_PLATFORM: `${IPC_PREFIX}app:getPlatform`,

  // Window controls
  WINDOW_MINIMIZE: `${IPC_PREFIX}window:minimize`,
  WINDOW_MAXIMIZE: `${IPC_PREFIX}window:maximize`,
  WINDOW_UNMAXIMIZE: `${IPC_PREFIX}window:unmaximize`,
  WINDOW_CLOSE: `${IPC_PREFIX}window:close`,
  WINDOW_IS_MAXIMIZED: `${IPC_PREFIX}window:isMaximized`,
  WINDOW_TOGGLE_MAXIMIZE: `${IPC_PREFIX}window:toggleMaximize`,
  WINDOW_STATE_CHANGE: `${IPC_PREFIX}window:stateChange`,

  // File system
  FS_READ_FILE: `${IPC_PREFIX}fs:readFile`,
  FS_WRITE_FILE: `${IPC_PREFIX}fs:writeFile`,
  FS_SHOW_OPEN_DIALOG: `${IPC_PREFIX}fs:showOpenDialog`,
  FS_SHOW_SAVE_DIALOG: `${IPC_PREFIX}fs:showSaveDialog`,
  FS_SHOW_ITEM_IN_FOLDER: `${IPC_PREFIX}fs:showItemInFolder`,

  // Shell
  SHELL_OPEN_EXTERNAL: `${IPC_PREFIX}shell:openExternal`,
  SHELL_OPEN_PATH: `${IPC_PREFIX}shell:openPath`,

  // Clipboard
  CLIPBOARD_READ_TEXT: `${IPC_PREFIX}clipboard:readText`,
  CLIPBOARD_WRITE_TEXT: `${IPC_PREFIX}clipboard:writeText`,

  // System info
  SYSTEM_GET_USER_INFO: `${IPC_PREFIX}system:getUserInfo`,
  SYSTEM_GET_PATHS: `${IPC_PREFIX}system:getPaths`,

  // Navigation (main -> renderer)
  NAVIGATE: `${IPC_PREFIX}navigate`,

  // Auto-update
  UPDATER_CHECK: `${IPC_PREFIX}updater:check`,
  UPDATER_DOWNLOAD: `${IPC_PREFIX}updater:download`,
  UPDATER_INSTALL: `${IPC_PREFIX}updater:install`,
  UPDATER_STATE_CHANGE: `${IPC_PREFIX}updater:stateChange`,

  // === Frontend integration APIs ===

  // Frontend integration channels use the same namespace as every IPC surface.
  FIRST_LAUNCH_COMPLETE: `${IPC_PREFIX}first-launch:complete`,

  MODEL_DOWNLOAD: `${IPC_PREFIX}model:download`,

  BACKEND_URL_CHANGED: `${IPC_PREFIX}backend:url-changed`,

  // Backend URL & runtime info
  BACKEND_GET_URL: `${IPC_PREFIX}backend:getUrl`,
  BACKEND_GET_RUNTIME: `${IPC_PREFIX}backend:getRuntime`,

  // Directory chooser dialog
  DIALOG_CHOOSE_DIRECTORY: `${IPC_PREFIX}dialog:chooseDirectory`,

  // Settings persistence
  SETTINGS_SAVE: `${IPC_PREFIX}settings:save`,

  // System notification
  NOTIFICATION_SHOW: `${IPC_PREFIX}notification:show`,
} as const

export type IpcChannel = typeof IPC_CHANNELS[keyof typeof IPC_CHANNELS]
