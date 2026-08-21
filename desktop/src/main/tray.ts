import { Tray, Menu, BrowserWindow, nativeImage, app } from 'electron'
import path from 'path'
import { APP_NAME } from './constants'

let tray: Tray | null = null

/**
 * Create the system tray icon with context menu.
 */
export function createTray(onShow: () => void, onQuit: () => void): Tray {
  // Use a small 16x16 image for tray (icon.png is the main icon)
  // Fallback to empty image if not available
  let image = nativeImage.createEmpty()
  const iconPath = path.join(__dirname, '../../resources/icons/tray.png')
  try {
    image = nativeImage.createFromPath(iconPath)
    if (image.isEmpty()) {
      // Create a 16x16 colored placeholder
      image = nativeImage.createFromBuffer(Buffer.from(
        'iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAQklEQVQ4y2NkYPj/n4EKgBmAywYmBgYGcAbG' +
          'JsYmRgZGJkYmBiZGBgYWRgYmRgZGBkYGQAFjAXMDEwMTADtQCQM1g8AXFIEiLn0B2WAAAAAElFTkSuQmCC',
        'base64'
      ))
    }
  } catch {
    // Use empty image
  }

  // macOS: mark as template so it adapts to dark/light
  if (process.platform === 'darwin') {
    image.setTemplateImage(true)
  }

  tray = new Tray(image)
  tray.setToolTip(APP_NAME)

  const contextMenu = Menu.buildFromTemplate([
    { label: APP_NAME, enabled: false },
    { type: 'separator' },
    {
      label: '显示主窗口',
      click: onShow,
    },
    {
      label: '新建项目',
      click: () => {
        const win = BrowserWindow.getFocusedWindow()
        if (win) {
          win.webContents.send('cs:navigate', '/projects/new')
        }
      },
    },
    { type: 'separator' },
    {
      label: '退出',
      click: onQuit,
    },
  ])

  tray.setContextMenu(contextMenu)

  // Click on tray icon shows the window
  tray.on('click', onShow)

  return tray
}

/**
 * Destroy the tray icon (called on app quit).
 */
export function destroyTray(): void {
  if (tray) {
    tray.destroy()
    tray = null
  }
}
