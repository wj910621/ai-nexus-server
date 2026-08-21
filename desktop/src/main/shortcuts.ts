import { globalShortcut, BrowserWindow } from 'electron'

/**
 * Register global keyboard shortcuts.
 * Returns an unregister function.
 */
export function registerGlobalShortcuts(shortcuts: {
  onToggleWindow?: () => void
  onNewProject?: () => void
} = {}): () => void {
  const registered: string[] = []

  if (shortcuts.onToggleWindow) {
    const accel = 'CommandOrControl+Shift+C'
    globalShortcut.register(accel, shortcuts.onToggleWindow)
    registered.push(accel)
  }

  if (shortcuts.onNewProject) {
    const accel = 'CommandOrControl+Shift+N'
    globalShortcut.register(accel, shortcuts.onNewProject)
    registered.push(accel)
  }

  return () => {
    for (const accel of registered) {
      globalShortcut.unregister(accel)
    }
  }
}

/**
 * Unregister all global shortcuts (called on app quit).
 */
export function unregisterAllShortcuts(): void {
  globalShortcut.unregisterAll()
}
