import { ipcMain } from 'electron'
import { registerFsHandlers } from './fs'
import { registerSystemHandlers } from './system'
import { registerWindowHandlers } from './window'
import { registerShellHandlers } from './shell'
import { registerUpdaterHandlers } from './updater'
import { registerIntegrationHandlers } from './integration'

/**
 * Register all IPC handlers in the main process.
 * Must be called after app.whenReady().
 */
export function registerAllIpcHandlers(): void {
  registerFsHandlers()
  registerSystemHandlers()
  registerWindowHandlers()
  registerShellHandlers()
  registerUpdaterHandlers()
  registerIntegrationHandlers()
}
