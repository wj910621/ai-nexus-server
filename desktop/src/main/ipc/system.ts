import { ipcMain, app } from 'electron'
import * as os from 'os'
import { IPC_CHANNELS } from '@shared/ipc-channels'

export function registerSystemHandlers(): void {
  ipcMain.handle(IPC_CHANNELS.APP_GET_VERSION, () => app.getVersion())
  ipcMain.handle(IPC_CHANNELS.APP_GET_PLATFORM, () => process.platform)

  ipcMain.handle(IPC_CHANNELS.SYSTEM_GET_USER_INFO, () => {
    const info = os.userInfo()
    return {
      username: info.username,
      homedir: info.homedir,
      platform: process.platform,
    }
  })

  ipcMain.handle(IPC_CHANNELS.SYSTEM_GET_PATHS, (_event, names: string[]) => {
    const result: Record<string, string> = {}
    for (const name of names) {
      try {
        result[name] = app.getPath(name as any)
      } catch {
        result[name] = ''
      }
    }
    return result
  })
}
