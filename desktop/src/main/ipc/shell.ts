import { ipcMain, shell, clipboard } from 'electron'
import { IPC_CHANNELS } from '@shared/ipc-channels'

export function registerShellHandlers(): void {
  // URL validation: only allow http/https
  ipcMain.handle(IPC_CHANNELS.SHELL_OPEN_EXTERNAL, async (_event, url: string) => {
    const parsed = new URL(url)
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      throw new Error(`Refused to open URL with protocol: ${parsed.protocol}`)
    }
    await shell.openExternal(url)
  })

  ipcMain.handle(IPC_CHANNELS.SHELL_OPEN_PATH, async (_event, path: string) => {
    const errorMessage = await shell.openPath(path)
    if (errorMessage) {
      throw new Error(errorMessage)
    }
    return path
  })

  ipcMain.handle(IPC_CHANNELS.CLIPBOARD_READ_TEXT, () => {
    return clipboard.readText()
  })

  ipcMain.handle(IPC_CHANNELS.CLIPBOARD_WRITE_TEXT, (_event, text: string) => {
    clipboard.writeText(text)
  })
}
