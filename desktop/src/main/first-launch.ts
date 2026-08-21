import { BrowserWindow, ipcMain, app } from 'electron'
import Store from 'electron-store'
import { DEV_SERVER_URL, PROD_RENDERER_ENTRY } from './constants'
import { createMainWindow, getMainWindow } from './window'
import { IPC_CHANNELS } from '@shared/ipc-channels'

const store = new Store<{ firstLaunchCompleted: boolean }>({
  defaults: { firstLaunchCompleted: false },
})

/**
 * Check whether the first-launch wizard should be shown.
 */
export function shouldShowFirstLaunch(): boolean {
  return !store.get('firstLaunchCompleted')
}

/**
 * Load the first-launch wizard page via hash routing (reuses the main renderer).
 */
export function loadFirstLaunch(mainWindow: BrowserWindow): void {
  const isDev = !app.isPackaged
  if (isDev) {
    mainWindow.loadURL(`${DEV_SERVER_URL}#/first-launch`)
  } else {
    mainWindow.loadFile(PROD_RENDERER_ENTRY, { hash: '/first-launch' })
  }
}

/**
 * Register IPC handlers related to the first-launch wizard.
 * Must be called after app.whenReady().
 */
export function registerFirstLaunchHandlers(): void {
  ipcMain.handle(IPC_CHANNELS.FIRST_LAUNCH_COMPLETE, async () => {
    store.set('firstLaunchCompleted', true)

    // Load the main page
    const mainWindow = getMainWindow()
    if (mainWindow) {
      const isDev = !app.isPackaged
      if (isDev) {
        mainWindow.loadURL(DEV_SERVER_URL)
      } else {
        mainWindow.loadFile(PROD_RENDERER_ENTRY)
      }
    }
    return true
  })
}
