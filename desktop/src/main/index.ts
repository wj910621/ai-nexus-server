import { app, BrowserWindow, dialog } from 'electron'
import { createMainWindow, getMainWindow } from './window'
import { setupMenu } from './menu'
import { APP_NAME } from './constants'
import { registerAllIpcHandlers } from './ipc'
import { createTray, destroyTray } from './tray'
import { setupDeepLink } from './deep-link'
import { registerGlobalShortcuts, unregisterAllShortcuts } from './shortcuts'
import { showNotification } from './notifications'
import { initAutoUpdater, onUpdaterStateChange } from './updater'
import { getBackendProcess } from './backend'
import { BACKEND_MODE } from './constants'
import { shouldShowFirstLaunch, loadFirstLaunch, registerFirstLaunchHandlers } from './first-launch'

// Single instance lock
const gotTheLock = app.requestSingleInstanceLock()

if (!gotTheLock) {
  app.quit()
} else {
  app.on('second-instance', () => {
    const win = getMainWindow()
    if (win) {
      if (win.isMinimized()) win.restore()
      win.focus()
    }
  })

  app.whenReady().then(() => {
    // Set app user model id for Windows taskbar
    if (process.platform === 'win32') {
      app.setAppUserModelId('com.comicstudio.ai')
    }

    // Register IPC handlers
    registerAllIpcHandlers()
    // Register first-launch IPC handlers (must come after the above)
    registerFirstLaunchHandlers()

    // Setup menu
    setupMenu({
      onAbout: showAboutDialog,
      onSettings: () => {
        const win = getMainWindow()
        if (win) {
          win.webContents.send('navigate', '/settings')
        }
      },
      onNewWindow: () => {
        const win = getMainWindow()
        if (win) {
          win.webContents.send('navigate', '/projects/new')
        }
      },
    })

    // Create main window
    const mainWindow = createMainWindow()

    // Show first-launch wizard on first run; otherwise the window already
    // loaded the default page inside createMainWindow().
    if (shouldShowFirstLaunch()) {
      loadFirstLaunch(mainWindow)
    }

    // Initialize auto-updater (only effective in packaged mode)
    initAutoUpdater()
    onUpdaterStateChange((state) => {
      const win = getMainWindow()
      if (win && state.status === 'available') {
        showNotification('发现新版本', `版本 ${state.info.version} 可用，请前往帮助菜单更新`)
      }
    })
    // Check for updates on startup (silent)
    if (app.isPackaged) {
      import('./updater').then(({ checkForUpdates }) => checkForUpdates().catch(() => {}))
    }

    // Start backend in local-python mode
    if (BACKEND_MODE === 'local-python') {
      const backend = getBackendProcess()
      backend.on('status', (status) => {
        if (status === 'failed') {
          showNotification('后端启动失败', '请检查 Python 环境配置')
        } else if (status === 'running') {
          showNotification('后端已就绪', 'Y·NEX Story Studio 后端服务已启动')
        }
      })
      backend.start().catch((e) => {
        console.error('Failed to start backend:', e)
      })
    }

    // Setup deep link handling
    setupDeepLink((routerPath) => {
      const win = getMainWindow()
      if (win) {
        if (win.isMinimized()) win.restore()
        win.focus()
        win.webContents.send('cs:navigate', routerPath)
      }
    })

    // Create tray icon
    createTray(
      () => {
        const win = getMainWindow()
        if (win) {
          if (win.isMinimized()) win.restore()
          win.show()
          win.focus()
        }
      },
      () => app.quit()
    )

    // Register global shortcuts
    const unregisterShortcuts = registerGlobalShortcuts({
      onToggleWindow: () => {
        const win = getMainWindow()
        if (!win) return
        if (win.isVisible() && win.isFocused()) {
          win.hide()
        } else {
          win.show()
          win.focus()
        }
      },
      onNewProject: () => {
        const win = getMainWindow()
        if (win) {
          win.show()
          win.focus()
          win.webContents.send('cs:navigate', '/projects/new')
        }
      },
    })

    // macOS: re-create window when dock icon clicked and no windows open
    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        createMainWindow()
      }
    })
  })

  // Quit when all windows closed (except on macOS)
  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
      app.quit()
    }
  })

  // Cleanup on quit
  app.on('before-quit', async () => {
    unregisterAllShortcuts()
    destroyTray()
    // Stop backend if we started it
    if (BACKEND_MODE === 'local-python') {
      const backend = getBackendProcess()
      if (backend.isRunning()) {
        await backend.stop()
      }
    }
  })

  // Prevent tray icon from being GC'd
  process.on('exit', () => {
    destroyTray()
  })
}

/**
 * Show the About dialog.
 */
function showAboutDialog(): void {
  const win = getMainWindow()
  if (!win) return

  dialog.showMessageBox(win, {
    type: 'info',
    title: `关于 ${APP_NAME}`,
    message: APP_NAME,
    detail: [
      `版本: ${app.getVersion()}`,
      `Electron: ${process.versions.electron}`,
      `Chrome: ${process.versions.chrome}`,
      `Node.js: ${process.versions.node}`,
      '',
      '一款商业化的综合型漫剧生成软件',
      'Powered by Y·NEX',
    ].join('\n'),
    buttons: ['确定'],
    icon: undefined,
  })
}
