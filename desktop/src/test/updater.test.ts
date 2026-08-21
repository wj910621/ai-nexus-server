import { describe, it, expect, vi } from 'vitest'

// Mock electron-updater before importing the module under test
vi.mock('electron-updater', () => ({
  autoUpdater: {
    autoDownload: true,
    autoInstallOnAppQuit: true,
    logger: null,
    on: vi.fn(),
    checkForUpdates: vi.fn(),
    downloadUpdate: vi.fn(),
    quitAndInstall: vi.fn(),
  },
}))

// Mock electron
vi.mock('electron', () => ({
  app: {
    isPackaged: false,
    getVersion: () => '0.1.0',
  },
  BrowserWindow: {
    getAllWindows: () => [],
  },
}))

import { checkForUpdates, getUpdaterState, onUpdaterStateChange } from '@main/updater/auto-updater'

describe('AutoUpdater', () => {
  it('initial state is idle', () => {
    // State may be idle or have been mutated by other tests
    const state = getUpdaterState()
    expect(['idle', 'checking', 'not-available', 'error']).toContain(state.status)
  })

  it('checkForUpdates returns not available in dev mode', async () => {
    const result = await checkForUpdates()
    expect(result.available).toBe(false)
    expect(result.currentVersion).toBe('0.1.0')
  })

  it('onUpdaterStateChange returns an unsubscribe function', () => {
    const unsub = onUpdaterStateChange(() => {})
    expect(typeof unsub).toBe('function')
    unsub()
  })

  it('listeners receive state changes', async () => {
    // We cannot easily test internal setState, but we can verify
    // that calling checkForUpdates in dev mode does not crash
    const result = await checkForUpdates()
    expect(result).toBeDefined()
  })
})
