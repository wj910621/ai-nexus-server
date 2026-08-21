import { autoUpdater } from 'electron-updater'
import { app } from 'electron'
import type { UpdaterState, UpdateCheckResult } from '@shared/types'
import { IPC_CHANNELS } from '@shared/ipc-channels'
import { BrowserWindow } from 'electron'

let currentState: UpdaterState = { status: 'idle' }
let listeners: ((state: UpdaterState) => void)[] = []
let initialized = false

/**
 * Initialize the auto-updater.
 * Must be called after app.whenReady() and only in packaged mode.
 */
export function initAutoUpdater(): void {
  if (initialized) return
  if (!app.isPackaged) {
    // Skip auto-updater in development
    console.log('[AutoUpdater] Skipped in development mode')
    return
  }
  initialized = true

  autoUpdater.autoDownload = false
  autoUpdater.autoInstallOnAppQuit = false
  autoUpdater.logger = console

  autoUpdater.on('checking-for-update', () => {
    setState({ status: 'checking' })
  })

  autoUpdater.on('update-available', (info) => {
    setState({
      status: 'available',
      info: {
        version: info.version,
        releaseNotes: typeof info.releaseNotes === 'string' ? info.releaseNotes : undefined,
      },
    })
  })

  autoUpdater.on('update-not-available', () => {
    setState({ status: 'not-available' })
  })

  autoUpdater.on('download-progress', (progress) => {
    setState({ status: 'downloading', percent: Math.round(progress.percent) })
  })

  autoUpdater.on('update-downloaded', () => {
    setState({ status: 'downloaded' })
  })

  autoUpdater.on('error', (err) => {
    setState({ status: 'error', message: err.message })
  })
}

/**
 * Check for updates.
 */
export async function checkForUpdates(): Promise<UpdateCheckResult> {
  if (!app.isPackaged) {
    return {
      available: false,
      currentVersion: app.getVersion(),
    }
  }

  try {
    const result = await autoUpdater.checkForUpdates()
    if (!result || !result.updateInfo) {
      return {
        available: false,
        currentVersion: app.getVersion(),
      }
    }
    return {
      available: true,
      currentVersion: app.getVersion(),
      latestVersion: result.updateInfo.version,
      releaseNotes:
        typeof result.updateInfo.releaseNotes === 'string'
          ? result.updateInfo.releaseNotes
          : undefined,
      releaseUrl: undefined,
    }
  } catch (e) {
    setState({ status: 'error', message: (e as Error).message })
    return {
      available: false,
      currentVersion: app.getVersion(),
    }
  }
}

/**
 * Download the available update.
 */
export async function downloadUpdate(): Promise<void> {
  if (!app.isPackaged) {
    throw new Error('Cannot download updates in development mode')
  }
  await autoUpdater.downloadUpdate()
}

/**
 * Quit and install the downloaded update.
 */
export async function installUpdate(): Promise<void> {
  if (!app.isPackaged) {
    throw new Error('Cannot install updates in development mode')
  }
  // setImmediate ensures the renderer has time to react
  setImmediate(() => {
    autoUpdater.quitAndInstall()
  })
}

/**
 * Get the current updater state.
 */
export function getUpdaterState(): UpdaterState {
  return currentState
}

/**
 * Subscribe to updater state changes.
 * Returns an unsubscribe function.
 */
export function onUpdaterStateChange(listener: (state: UpdaterState) => void): () => void {
  listeners.push(listener)
  return () => {
    listeners = listeners.filter((l) => l !== listener)
  }
}

function setState(state: UpdaterState): void {
  currentState = state
  for (const listener of listeners) {
    listener(state)
  }
  // Also broadcast to all renderer windows
  for (const win of BrowserWindow.getAllWindows()) {
    win.webContents.send(IPC_CHANNELS.UPDATER_STATE_CHANGE, state)
  }
}
