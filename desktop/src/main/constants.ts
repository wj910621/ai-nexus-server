// Application constants
export const APP_NAME = 'Y·NEX Story Studio'
export const APP_VERSION = '0.1.0'

// Window defaults
export const WINDOW_DEFAULTS = {
  width: 1440,
  height: 900,
  minWidth: 1024,
  minHeight: 768,
  backgroundColor: '#1e1e2e',
  show: false,
} as const

// Dev server URL (Vite default port)
export const DEV_SERVER_URL = 'http://localhost:5173'

// Production renderer entry (built by electron-vite)
export const PROD_RENDERER_ENTRY = '../renderer/index.html'

// Backend default URL (Phase 4: desktop connects to existing backend, not bundled)
export const BACKEND_URL = process.env.VITE_API_BASE_URL || 'http://localhost:8000'

// IPC channel namespace prefix to avoid collisions
export const IPC_PREFIX = 'cs:'

// Backend process management
export const BACKEND_HEALTH_ENDPOINT = '/health'
export const BACKEND_STARTUP_TIMEOUT_MS = 60_000   // 60s to start
export const BACKEND_HEALTH_INTERVAL_MS = 2_000    // poll every 2s
export const BACKEND_SHUTDOWN_TIMEOUT_MS = 10_000  // 10s to shutdown gracefully

// Backend process mode
export type BackendMode = 'remote' | 'local-python' | 'disabled'

export const BACKEND_MODE: BackendMode =
  (process.env.CS_BACKEND_MODE as BackendMode) || 'remote'

// Local backend spawn configuration (only used when mode = 'local-python')
export const LOCAL_BACKEND_CONFIG = {
  // Path to backend directory relative to desktop/
  backendDir: process.env.CS_BACKEND_DIR || '../../backend',
  // Python executable (venv preferred if available)
  pythonExecutable: process.env.CS_PYTHON || 'python',
  // uvicorn module and app target
  module: 'uvicorn',
  appTarget: 'app.main:app',
  host: '127.0.0.1',
  port: 8000,
} as const

// Packaged backend executable (Phase 5: PyInstaller-built)
// When mode = 'local-python' and this path exists, spawn it directly.
// Otherwise fall back to python source mode.
export const PACKAGED_BACKEND_CONFIG = {
  // Path to packaged backend dir, relative to desktop/
  packagedDir: process.env.CS_PACKAGED_BACKEND_DIR || '../backend/dist/comicstudio-backend',
  // Executable name (no extension; .exe added on Windows)
  executableName: 'comicstudio-backend',
  // Host/port passed as CLI args
  host: '127.0.0.1',
  port: 8000,
} as const

// Resolve the actual executable path based on platform
export function getPackagedBackendPath(): string {
  const path = require('path') as typeof import('path')
  const exeName = process.platform === 'win32'
    ? `${PACKAGED_BACKEND_CONFIG.executableName}.exe`
    : PACKAGED_BACKEND_CONFIG.executableName

  // 1. Explicit env override (testing)
  if (process.env.CS_PACKAGED_BACKEND_PATH) {
    return process.env.CS_PACKAGED_BACKEND_PATH
  }

  // 2. Packaged Electron app: extraResources lands in process.resourcesPath
  if (process.resourcesPath) {
    const resourcesCandidate = path.join(
      process.resourcesPath,
      'comicstudio-backend',
      exeName
    )
    // Check existence synchronously (cheap)
    try {
      const fs = require('fs') as typeof import('fs')
      if (fs.existsSync(resourcesCandidate)) {
        return resourcesCandidate
      }
    } catch {
      // ignore
    }
  }

  // 3. Development: resolve from backend/dist/
  return path.resolve(
    __dirname,
    '..',
    '..',
    '..',
    PACKAGED_BACKEND_CONFIG.packagedDir,
    exeName
  )
}
