import { ipcMain, dialog, BrowserWindow } from 'electron'
import Store from 'electron-store'
import { IPC_CHANNELS } from '@shared/ipc-channels'
import type { SaveSettingsPayload, NotificationPayload, RuntimeInfo } from '@shared/types'
import { getBackendPort } from '../backend'
import { showNotification } from '../notifications'

// Persistent settings store shared with the preload layer.
const settingsStore = new Store<{
  dataDir?: string
  telemetry?: boolean
  autoUpdate?: boolean
}>({ defaults: { telemetry: true, autoUpdate: true } })

/**
 * Register IPC handlers for frontend integration APIs.
 * Must be called after app.whenReady().
 */
export function registerIntegrationHandlers(): void {
  // Return the backend URL the renderer should call.
  ipcMain.handle(IPC_CHANNELS.BACKEND_GET_URL, () => {
    const port = getBackendPort()
    return `http://127.0.0.1:${port}`
  })

  // Fetch runtime info from the backend.
  ipcMain.handle(IPC_CHANNELS.BACKEND_GET_RUNTIME, async () => {
    const port = getBackendPort()
    const resp = await fetch(`http://127.0.0.1:${port}/api/v1/models/runtime`)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    return (await resp.json()) as RuntimeInfo
  })

  // Open a directory picker dialog.
  ipcMain.handle(IPC_CHANNELS.DIALOG_CHOOSE_DIRECTORY, async (event) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    const result = await dialog.showOpenDialog(win!, {
      properties: ['openDirectory'],
    })
    return result.canceled ? null : result.filePaths[0]
  })

  // Persist user settings via electron-store.
  ipcMain.handle(
    IPC_CHANNELS.SETTINGS_SAVE,
    async (_event, settings: SaveSettingsPayload) => {
      if (settings.dataDir !== undefined) settingsStore.set('dataDir', settings.dataDir)
      if (settings.telemetry !== undefined) settingsStore.set('telemetry', settings.telemetry)
      if (settings.autoUpdate !== undefined) settingsStore.set('autoUpdate', settings.autoUpdate)
    }
  )

  // Trigger a model download via the backend API.
  ipcMain.handle(IPC_CHANNELS.MODEL_DOWNLOAD, async (_event, name: string) => {
    const port = getBackendPort()
    const resp = await fetch(
      `http://127.0.0.1:${port}/api/v1/models/${encodeURIComponent(name)}/download`,
      { method: 'POST' }
    )
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
  })

  // Show a desktop notification via the main process.
  ipcMain.handle(
    IPC_CHANNELS.NOTIFICATION_SHOW,
    async (_event, notification: NotificationPayload) => {
      showNotification(notification.title, notification.body)
    }
  )
}
