import { ipcMain, BrowserWindow } from 'electron'
import { IPC_CHANNELS } from '@shared/ipc-channels'
import type { WindowState } from '@shared/types'
import { getMainWindow } from '../window'

export function registerWindowHandlers(): void {
  ipcMain.handle(IPC_CHANNELS.WINDOW_MINIMIZE, () => {
    getMainWindow()?.minimize()
  })

  ipcMain.handle(IPC_CHANNELS.WINDOW_MAXIMIZE, () => {
    getMainWindow()?.maximize()
  })

  ipcMain.handle(IPC_CHANNELS.WINDOW_UNMAXIMIZE, () => {
    getMainWindow()?.unmaximize()
  })

  ipcMain.handle(IPC_CHANNELS.WINDOW_CLOSE, () => {
    getMainWindow()?.close()
  })

  ipcMain.handle(IPC_CHANNELS.WINDOW_TOGGLE_MAXIMIZE, () => {
    const win = getMainWindow()
    if (!win) return
    if (win.isMaximized()) {
      win.unmaximize()
    } else {
      win.maximize()
    }
  })

  ipcMain.handle(IPC_CHANNELS.WINDOW_IS_MAXIMIZED, () => {
    return getMainWindow()?.isMaximized() ?? false
  })

  // Emit state change events to all web contents
  const emitState = () => {
    const win = getMainWindow()
    if (!win) return
    const state: WindowState = {
      isMaximized: win.isMaximized(),
      isMinimized: win.isMinimized(),
      isFullScreen: win.isFullScreen(),
    }
    win.webContents.send(IPC_CHANNELS.WINDOW_STATE_CHANGE, state)
  }

  // Attach listeners to the main window after it's created
  // (called from window.ts after window creation)
  app.on('browser-window-created', (_event, win) => {
    win.on('maximize', emitState)
    win.on('unmaximize', emitState)
    win.on('minimize', emitState)
    win.on('restore', emitState)
    win.on('enter-full-screen', emitState)
    win.on('leave-full-screen', emitState)
  })
}

// Need to import app for the browser-window-created listener
import { app } from 'electron'
