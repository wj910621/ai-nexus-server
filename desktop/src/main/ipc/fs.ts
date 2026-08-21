import { ipcMain, dialog, shell, BrowserWindow } from 'electron'
import * as fs from 'fs/promises'
import { IPC_CHANNELS } from '@shared/ipc-channels'
import type { OpenDialogOptions, SaveDialogOptions } from '@shared/types'

export function registerFsHandlers(): void {
  ipcMain.handle(IPC_CHANNELS.FS_READ_FILE, async (_event, { path, encoding }) => {
    const content = await fs.readFile(path, { encoding: encoding || 'utf-8' })
    return { path, content, encoding: encoding || 'utf-8' }
  })

  ipcMain.handle(IPC_CHANNELS.FS_WRITE_FILE, async (_event, { path, content, encoding }) => {
    await fs.writeFile(path, content, { encoding: encoding || 'utf-8' })
  })

  ipcMain.handle(IPC_CHANNELS.FS_SHOW_OPEN_DIALOG, async (event, options: OpenDialogOptions) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    if (!win) return null
    const result = await dialog.showOpenDialog(win, {
      title: options.title,
      defaultPath: options.defaultPath,
      filters: options.filters,
      properties: options.properties as any,
    })
    if (result.canceled || result.filePaths.length === 0) return null
    return result.filePaths[0]
  })

  ipcMain.handle(IPC_CHANNELS.FS_SHOW_SAVE_DIALOG, async (event, options: SaveDialogOptions) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    if (!win) return null
    const result = await dialog.showSaveDialog(win, {
      title: options.title,
      defaultPath: options.defaultPath,
      filters: options.filters,
    })
    if (result.canceled) return null
    return result.filePath
  })

  ipcMain.handle(IPC_CHANNELS.FS_SHOW_ITEM_IN_FOLDER, async (_event, path: string) => {
    shell.showItemInFolder(path)
  })
}
