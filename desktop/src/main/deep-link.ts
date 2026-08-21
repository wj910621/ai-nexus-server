import { app } from 'electron'

export const DEEP_LINK_PROTOCOL = 'comicstudio'

/**
 * Parse a deep link URL into a structured path.
 * Examples:
 *   comicstudio://projects/abc        -> { action: 'projects', params: { id: 'abc' } }
 *   comicstudio://workflow/run/xyz     -> { action: 'workflow', params: { sub: 'run', id: 'xyz' } }
 *   comicstudio://settings            -> { action: 'settings', params: {} }
 *
 * Pure function for testability.
 */
export function parseDeepLink(url: string): { action: string; params: Record<string, string> } {
  if (!url.startsWith(`${DEEP_LINK_PROTOCOL}://`)) {
    throw new Error(`Invalid deep link protocol: ${url}`)
  }

  const pathPart = url.slice(`${DEEP_LINK_PROTOCOL}://`.length)
  // Strip query string if present
  const [pathOnly] = pathPart.split('?')
  const segments = pathOnly.split('/').filter((s) => s.length > 0)

  if (segments.length === 0) {
    return { action: 'home', params: {} }
  }

  const action = segments[0]
  const params: Record<string, string> = {}

  if (segments.length === 2) {
    params.id = segments[1]
  } else if (segments.length >= 3) {
    params.sub = segments[1]
    params.id = segments[2]
  }

  return { action, params }
}

/**
 * Convert a parsed deep link into a router path for the renderer.
 */
export function deepLinkToRouterPath(parsed: { action: string; params: Record<string, string> }): string {
  switch (parsed.action) {
    case 'home':
      return '/dashboard'
    case 'projects':
      return parsed.params.id ? `/projects/${parsed.params.id}` : '/projects'
    case 'workflow':
      if (parsed.params.sub === 'run' && parsed.params.id) {
        return `/projects/${parsed.params.id}`
      }
      return '/dashboard'
    case 'settings':
      return '/settings'
    case 'characters':
      return '/characters'
    default:
      return '/dashboard'
  }
}

/**
 * Register the deep link protocol handler.
 * Must be called before app.whenReady().
 */
export function setupDeepLink(onOpen: (routerPath: string) => void): void {
  // Set as default protocol client
  if (process.defaultApp) {
    if (process.argv.length >= 2) {
      app.setAsDefaultProtocolClient(DEEP_LINK_PROTOCOL, process.execPath, [
        path.resolve(process.argv[1]),
      ])
    }
  } else {
    app.setAsDefaultProtocolClient(DEEP_LINK_PROTOCOL)
  }

  // Handle macOS open-url event
  app.on('open-url', (event, url) => {
    event.preventDefault()
    try {
      const parsed = parseDeepLink(url)
      const routerPath = deepLinkToRouterPath(parsed)
      onOpen(routerPath)
    } catch (e) {
      console.error('Failed to parse deep link:', e)
    }
  })

  // Handle Windows/Linux second-instance with deep link
  app.on('second-instance', (_event, argv) => {
    const deepLinkUrl = argv.find((arg) => arg.startsWith(`${DEEP_LINK_PROTOCOL}://`))
    if (deepLinkUrl) {
      try {
        const parsed = parseDeepLink(deepLinkUrl)
        const routerPath = deepLinkToRouterPath(parsed)
        onOpen(routerPath)
      } catch (e) {
        console.error('Failed to parse deep link:', e)
      }
    }
  })
}

import path from 'path'
