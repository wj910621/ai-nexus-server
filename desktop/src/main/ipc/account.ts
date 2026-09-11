/**
 * P1 统一账号层 —— IPC handlers（主进程侧）
 * 通道常量见 @shared/ipc-channels
 */
import { ipcMain } from 'electron'
import { IPC_CHANNELS } from '@shared/ipc-channels'
import { createAccountService } from '../services/account-service'

let svc: ReturnType<typeof createAccountService> | null = null

function service(): ReturnType<typeof createAccountService> {
  if (!svc) svc = createAccountService()
  return svc
}

export function registerAccountHandlers(): void {
  ipcMain.handle(IPC_CHANNELS.ACCOUNT_LOGIN, async (_e, args: { username?: string; password?: string }) => {
    return service().login(args?.username ?? '', args?.password ?? '')
  })
  ipcMain.handle(IPC_CHANNELS.ACCOUNT_ME, async () => {
    return service().me()
  })
  ipcMain.handle(IPC_CHANNELS.ACCOUNT_LOGOUT, async () => {
    return service().logout()
  })
  ipcMain.handle(IPC_CHANNELS.ACCOUNT_STORY_TOKEN, async () => {
    return service().storyToken()
  })
}
