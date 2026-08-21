import { Notification, BrowserWindow } from 'electron'
import { APP_NAME } from './constants'

/**
 * Show a desktop notification.
 * On macOS, the notification is delivered via Notification Center.
 * On Windows, via the Action Center.
 */
export function showNotification(title: string, body: string, onClick?: () => void): void {
  if (!Notification.isSupported()) {
    // Fallback: focus the window and use console
    console.warn(`[Notification unsupported] ${title}: ${body}`)
    return
  }

  const notification = new Notification({
    title,
    body,
    silent: false,
  })

  if (onClick) {
    notification.on('click', () => {
      const win = BrowserWindow.getFocusedWindow()
      if (win) {
        if (win.isMinimized()) win.restore()
        win.focus()
      }
      onClick()
    })
  }

  notification.show()
}

/**
 * Notify the user that an operation completed.
 */
export function notifyComplete(title: string, body: string): void {
  showNotification(`${APP_NAME} - ${title}`, body)
}

/**
 * Notify the user of an error.
 */
export function notifyError(title: string, body: string): void {
  showNotification(`${APP_NAME} - ${title}`, body)
}
