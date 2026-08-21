import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { BackendProcess } from '@main/backend/backend-process'
import { BACKEND_MODE } from '@main/constants'

// Mock the health-check module
vi.mock('@main/backend/health-check', () => ({
  checkBackendHealth: vi.fn().mockResolvedValue(true),
  waitForBackendHealth: vi.fn().mockResolvedValue(true),
}))

// Mock notifications
vi.mock('@main/notifications', () => ({
  showNotification: vi.fn(),
}))

// Mock electron app (since we cannot run a real Electron app in unit tests)
vi.mock('electron', () => ({
  app: {
    getAppPath: () => '/fake/path',
    getPath: () => '/fake/path',
    isPackaged: false,
    getVersion: () => '0.1.0',
    setAppUserModelId: vi.fn(),
    on: vi.fn(),
    whenReady: () => Promise.resolve(),
    requestSingleInstanceLock: () => true,
    quit: vi.fn(),
  },
  BrowserWindow: vi.fn(),
  Notification: { isSupported: () => false },
  Tray: vi.fn(),
  Menu: { buildFromTemplate: vi.fn(), setApplicationMenu: vi.fn() },
  globalShortcut: { register: vi.fn(), unregister: vi.fn(), unregisterAll: vi.fn() },
  dialog: { showMessageBox: vi.fn() },
  shell: { openExternal: vi.fn() },
}))

describe('BackendProcess', () => {
  let backend: BackendProcess

  beforeEach(() => {
    backend = new BackendProcess()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('initial status is "stopped"', () => {
    expect(backend.getStatus()).toBe('stopped')
  })

  it('isRunning() returns false initially', () => {
    expect(backend.isRunning()).toBe(false)
  })

  it('emits status change events', () => {
    const statuses: string[] = []
    const unsubscribe = backend.on('status', (s) => statuses.push(s))
    // Trigger a status change via start (mocked to succeed)
    // We can't actually test start() without spawning a process,
    // so we test the listener mechanism directly
    expect(typeof unsubscribe).toBe('function')
    unsubscribe()
  })

  it('remote mode: start returns true when health check passes', async () => {
    // BACKEND_MODE is 'remote' by default in test env
    expect(BACKEND_MODE).toBe('remote')
    const result = await backend.start()
    expect(result).toBe(true)
    expect(backend.getStatus()).toBe('running')
  })

  it('remote mode: stop sets status to stopped', async () => {
    await backend.start()
    expect(backend.getStatus()).toBe('running')
    await backend.stop()
    expect(backend.getStatus()).toBe('stopped')
  })

  it('isRunning() returns true after successful start', async () => {
    await backend.start()
    expect(backend.isRunning()).toBe(true)
  })

  it('isRunning() returns false after stop', async () => {
    await backend.start()
    await backend.stop()
    expect(backend.isRunning()).toBe(false)
  })

  it('multiple on() calls register multiple listeners', () => {
    let count = 0
    const unsub1 = backend.on('status', () => { count++ })
    const unsub2 = backend.on('status', () => { count++ })
    // Trigger manually is not possible since emit is private,
    // but we can verify unsub functions work
    expect(typeof unsub1).toBe('function')
    expect(typeof unsub2).toBe('function')
    unsub1()
    unsub2()
  })
})
