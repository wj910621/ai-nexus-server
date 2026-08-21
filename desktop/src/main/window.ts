import { BrowserWindow, shell } from 'electron'
import path from 'path'
import { WINDOW_DEFAULTS, DEV_SERVER_URL, PROD_RENDERER_ENTRY } from './constants'

let mainWindow: BrowserWindow | null = null

/**
 * Get the main window instance (may be null if not created yet).
 */
export function getMainWindow(): BrowserWindow | null {
  return mainWindow
}

/**
 * Create the main application window.
 * In dev mode loads the Vite dev server; in prod loads the built renderer.
 */
export function createMainWindow(): BrowserWindow {
  const isDev = !app.isPackaged

  const window = new BrowserWindow({
    ...WINDOW_DEFAULTS,
    title: 'Y·NEX Story Studio',
    icon: path.join(__dirname, '../../resources/icons/icon.png'),
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      webSecurity: !isDev,
    },
  })

  // Show window when ready (prevents flicker)
  window.once('ready-to-show', () => {
    window.show()
    if (isDev) {
      window.webContents.openDevTools({ mode: 'detach' })
    }
  })

  // Open external links in browser (not in-app)
  window.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })

  // Load content
  if (isDev) {
    window.loadURL(DEV_SERVER_URL)
  } else {
    window.loadFile(path.join(__dirname, PROD_RENDERER_ENTRY))
  }

  mainWindow = window
  return window
}

// app is imported here to avoid circular dependency issues at module load
import { app } from 'electron'
