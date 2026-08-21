import { ipcMain } from 'electron'
import { IPC_CHANNELS } from '@shared/ipc-channels'
import {
  checkForUpdates,
  downloadUpdate,
  installUpdate,
} from '../updater'

export function registerUpdaterHandlers(): void {
  ipcMain.handle(IPC_CHANNELS.UPDATER_CHECK, async () => {
    return checkForUpdates()
  })

  ipcMain.handle(IPC_CHANNELS.UPDATER_DOWNLOAD, async () => {
    await downloadUpdate()
  })

  ipcMain.handle(IPC_CHANNELS.UPDATER_INSTALL, async () => {
    await installUpdate()
  })
}
