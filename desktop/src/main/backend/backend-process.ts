import { ChildProcess, spawn } from 'child_process'
import path from 'path'
import { app } from 'electron'
import {
  BACKEND_MODE,
  LOCAL_BACKEND_CONFIG,
  BACKEND_STARTUP_TIMEOUT_MS,
  BACKEND_SHUTDOWN_TIMEOUT_MS,
  getPackagedBackendPath,
} from '../constants'
import { checkBackendHealth, waitForBackendHealth } from './health-check'
import { showNotification } from '../notifications'

export type BackendStatus = 'stopped' | 'starting' | 'running' | 'stopping' | 'failed'

export interface BackendLogEntry {
  stream: 'stdout' | 'stderr'
  data: string
  timestamp: number
}

type Listener<T extends keyof BackendEventMap> = (payload: BackendEventMap[T]) => void

interface BackendEventMap {
  status: BackendStatus
  log: BackendLogEntry
  error: { message: string; code?: number }
}

/**
 * Manages a Python backend child process.
 * In 'remote' mode, this class is a no-op (desktop connects to a remote backend).
 * In 'local-python' mode, it spawns a uvicorn subprocess.
 */
export class BackendProcess {
  private proc: ChildProcess | null = null
  private status: BackendStatus = 'stopped'
  private listeners: { [K in keyof BackendEventMap]?: Set<Listener<K>> } = {}

  /**
   * Current status of the backend.
   */
  getStatus(): BackendStatus {
    return this.status
  }

  /**
   * Whether the backend is currently running.
   */
  isRunning(): boolean {
    return this.status === 'running'
  }

  /**
   * Register an event listener.
   */
  on<K extends keyof BackendEventMap>(event: K, listener: Listener<K>): () => void {
    if (!this.listeners[event]) {
      this.listeners[event] = new Set() as any
    }
    ;(this.listeners[event] as Set<Listener<K>>).add(listener)
    return () => {
      ;(this.listeners[event] as Set<Listener<K>>)?.delete(listener)
    }
  }

  private emit<K extends keyof BackendEventMap>(event: K, payload: BackendEventMap[K]): void {
    ;(this.listeners[event] as Set<Listener<K>>)?.forEach((l) => l(payload))
  }

  private setStatus(status: BackendStatus): void {
    this.status = status
    this.emit('status', status)
  }

  /**
   * Start the backend.
   * In 'remote' mode, just checks if the remote backend is reachable.
   * In 'local-python' mode, spawns a uvicorn subprocess.
   */
  async start(): Promise<boolean> {
    if (BACKEND_MODE === 'remote' || BACKEND_MODE === 'disabled') {
      // Just verify the remote backend is reachable
      this.setStatus('starting')
      const healthy = await checkBackendHealth()
      if (healthy) {
        this.setStatus('running')
        return true
      }
      this.setStatus('failed')
      return false
    }

    if (this.proc && this.proc.exitCode === null) {
      // Already running
      return true
    }

    this.setStatus('starting')

    // Detect packaged backend mode: if the packaged exe exists, spawn it directly.
    // Otherwise fall back to python source mode (dev).
    const fs = await import('fs')
    const packagedExePath = getPackagedBackendPath()
    const usePackaged = fs.existsSync(packagedExePath)

    let command: string
    let args: string[]
    let cwd: string
    let env: NodeJS.ProcessEnv = { ...process.env, PYTHONUNBUFFERED: '1' }

    if (usePackaged) {
      // Packaged exe mode (Phase 5)
      command = packagedExePath
      args = [
        '--host', LOCAL_BACKEND_CONFIG.host,
        '--port', String(LOCAL_BACKEND_CONFIG.port),
      ]
      cwd = path.dirname(packagedExePath)
      env.CS_DESKTOP_MODE = '1'
      // Data dir: per-user userData
      env.CS_DATA_DIR = app.getPath('userData')
    } else {
      // Python source mode (dev fallback)
      const backendDir = path.resolve(app.getAppPath(), LOCAL_BACKEND_CONFIG.backendDir)
      command = LOCAL_BACKEND_CONFIG.pythonExecutable
      args = [
        '-m',
        LOCAL_BACKEND_CONFIG.module,
        LOCAL_BACKEND_CONFIG.appTarget,
        '--host',
        LOCAL_BACKEND_CONFIG.host,
        '--port',
        String(LOCAL_BACKEND_CONFIG.port),
      ]
      cwd = backendDir
    }

    try {
      this.proc = spawn(command, args, {
        cwd,
        env,
        stdio: ['ignore', 'pipe', 'pipe'],
      })
    } catch (e) {
      this.setStatus('failed')
      this.emit('error', { message: `Failed to spawn backend: ${(e as Error).message}` })
      return false
    }

    this.proc.stdout?.on('data', (data: Buffer) => {
      const text = data.toString('utf-8')
      this.emit('log', { stream: 'stdout', data: text, timestamp: Date.now() })
    })

    this.proc.stderr?.on('data', (data: Buffer) => {
      const text = data.toString('utf-8')
      this.emit('log', { stream: 'stderr', data: text, timestamp: Date.now() })
    })

    this.proc.on('exit', (code, signal) => {
      if (this.status !== 'stopping') {
        // Unexpected exit
        this.setStatus('failed')
        this.emit('error', {
          message: `Backend exited unexpectedly (code=${code}, signal=${signal})`,
          code: code ?? undefined,
        })
        showNotification('Y·NEX Story Studio - 后端异常', `后端进程退出 (code=${code})`)
      } else {
        this.setStatus('stopped')
      }
      this.proc = null
    })

    this.proc.on('error', (err) => {
      this.setStatus('failed')
      this.emit('error', { message: err.message })
    })

    // Wait for health check
    const healthy = await waitForBackendHealth(
      `http://${LOCAL_BACKEND_CONFIG.host}:${LOCAL_BACKEND_CONFIG.port}`,
      BACKEND_STARTUP_TIMEOUT_MS
    )

    // Log which mode was used (for debugging)
    if (usePackaged) {
      console.log('[backend] Started packaged executable:', packagedExePath)
    } else {
      console.log('[backend] Started python source mode')
    }

    if (healthy) {
      this.setStatus('running')
      return true
    }

    this.setStatus('failed')
    return false
  }

  /**
   * Stop the backend gracefully (SIGTERM then SIGKILL after timeout).
   */
  async stop(): Promise<void> {
    if (!this.proc || this.proc.exitCode !== null) {
      this.setStatus('stopped')
      return
    }

    this.setStatus('stopping')

    return new Promise<void>((resolve) => {
      const proc = this.proc!
      let resolved = false

      const killTimer = setTimeout(() => {
        if (!resolved && proc.exitCode === null) {
          proc.kill('SIGKILL')
        }
      }, BACKEND_SHUTDOWN_TIMEOUT_MS)

      proc.once('exit', () => {
        if (resolved) return
        resolved = true
        clearTimeout(killTimer)
        this.setStatus('stopped')
        this.proc = null
        resolve()
      })

      // Try graceful shutdown first
      proc.kill('SIGTERM')
    })
  }
}

// Singleton instance
let backendProcess: BackendProcess | null = null

export function getBackendProcess(): BackendProcess {
  if (!backendProcess) {
    backendProcess = new BackendProcess()
  }
  return backendProcess
}

/**
 * Get the configured backend port.
 * Used by IPC handlers and the preload bridge to build backend URLs.
 */
export function getBackendPort(): number {
  return LOCAL_BACKEND_CONFIG.port
}
