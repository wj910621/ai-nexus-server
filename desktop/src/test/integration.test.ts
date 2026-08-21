import { describe, it, expect } from 'vitest'
import * as fs from 'fs'
import * as path from 'path'

// Smoke tests: verify the project structure and configuration files are in place.
// These tests do NOT actually launch Electron (that requires an Electron runtime),
// but they verify that all source files exist and the build pipeline is configured.

const ROOT = path.resolve(__dirname, '../..')

describe('integration: project structure', () => {
  it('package.json exists and has required scripts', () => {
    const pkgPath = path.join(ROOT, 'package.json')
    expect(fs.existsSync(pkgPath)).toBe(true)
    const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf-8'))
    expect(pkg.scripts.dev).toBeDefined()
    expect(pkg.scripts.build).toBeDefined()
    expect(pkg.scripts['package:win']).toBeDefined()
    expect(pkg.scripts.icons).toBeDefined()
  })

  it('tsconfig.json exists', () => {
    expect(fs.existsSync(path.join(ROOT, 'tsconfig.json'))).toBe(true)
  })

  it('electron.vite.config.ts exists', () => {
    expect(fs.existsSync(path.join(ROOT, 'electron.vite.config.ts'))).toBe(true)
  })

  it('electron-builder.yml exists', () => {
    expect(fs.existsSync(path.join(ROOT, 'electron-builder.yml'))).toBe(true)
  })

  it('vitest.config.ts exists', () => {
    expect(fs.existsSync(path.join(ROOT, 'vitest.config.ts'))).toBe(true)
  })
})

describe('integration: source files', () => {
  it('main process entry exists', () => {
    expect(fs.existsSync(path.join(ROOT, 'src/main/index.ts'))).toBe(true)
  })

  it('preload entry exists', () => {
    expect(fs.existsSync(path.join(ROOT, 'src/preload/index.ts'))).toBe(true)
  })

  it('shared types exist', () => {
    expect(fs.existsSync(path.join(ROOT, 'src/shared/types.ts'))).toBe(true)
    expect(fs.existsSync(path.join(ROOT, 'src/shared/ipc-channels.ts'))).toBe(true)
  })

  it('IPC handlers exist', () => {
    expect(fs.existsSync(path.join(ROOT, 'src/main/ipc/index.ts'))).toBe(true)
    expect(fs.existsSync(path.join(ROOT, 'src/main/ipc/fs.ts'))).toBe(true)
    expect(fs.existsSync(path.join(ROOT, 'src/main/ipc/system.ts'))).toBe(true)
    expect(fs.existsSync(path.join(ROOT, 'src/main/ipc/window.ts'))).toBe(true)
    expect(fs.existsSync(path.join(ROOT, 'src/main/ipc/shell.ts'))).toBe(true)
    expect(fs.existsSync(path.join(ROOT, 'src/main/ipc/updater.ts'))).toBe(true)
  })

  it('system integration modules exist', () => {
    expect(fs.existsSync(path.join(ROOT, 'src/main/tray.ts'))).toBe(true)
    expect(fs.existsSync(path.join(ROOT, 'src/main/notifications.ts'))).toBe(true)
    expect(fs.existsSync(path.join(ROOT, 'src/main/deep-link.ts'))).toBe(true)
    expect(fs.existsSync(path.join(ROOT, 'src/main/shortcuts.ts'))).toBe(true)
  })

  it('backend process module exists', () => {
    expect(fs.existsSync(path.join(ROOT, 'src/main/backend/backend-process.ts'))).toBe(true)
    expect(fs.existsSync(path.join(ROOT, 'src/main/backend/health-check.ts'))).toBe(true)
  })

  it('updater module exists', () => {
    expect(fs.existsSync(path.join(ROOT, 'src/main/updater/auto-updater.ts'))).toBe(true)
  })

  it('icon generator script exists', () => {
    expect(fs.existsSync(path.join(ROOT, 'scripts/generate-icons.ts'))).toBe(true)
  })
})

describe('integration: build resources', () => {
  it('electron-builder.yml contains required top-level keys', () => {
    const yml = fs.readFileSync(path.join(ROOT, 'electron-builder.yml'), 'utf-8')
    expect(yml).toContain('appId:')
    expect(yml).toContain('productName:')
    expect(yml).toContain('directories:')
    expect(yml).toContain('files:')
    expect(yml).toContain('win:')
    expect(yml).toContain('nsis:')
    expect(yml).toContain('mac:')
    expect(yml).toContain('linux:')
    expect(yml).toContain('publish:')
  })

  it('NSIS installer customization exists', () => {
    expect(fs.existsSync(path.join(ROOT, 'build/installer.nsh'))).toBe(true)
  })

  it('README exists', () => {
    expect(fs.existsSync(path.join(ROOT, 'README.md'))).toBe(true)
  })
})

describe('integration: electron-builder config (light parse)', () => {
  it('appId is in reverse-DNS format', () => {
    const yml = fs.readFileSync(path.join(ROOT, 'electron-builder.yml'), 'utf-8')
    const match = yml.match(/appId:\s*(\S+)/)
    expect(match).not.toBeNull()
    expect(match![1]).toMatch(/^[a-z]+(\.[a-z]+)+$/)
  })

  it('productName contains the Y·NEX product brand', () => {
    const yml = fs.readFileSync(path.join(ROOT, 'electron-builder.yml'), 'utf-8')
    expect(yml).toMatch(/productName:\s*Y·NEX Story Studio/)
  })

  it('publish provider is github', () => {
    const yml = fs.readFileSync(path.join(ROOT, 'electron-builder.yml'), 'utf-8')
    expect(yml).toMatch(/provider:\s*github/)
  })
})

describe('Phase 5: Packaged backend configuration', () => {
  it('exports PACKAGED_BACKEND_CONFIG', async () => {
    const constants = await import('../main/constants')
    expect(constants.PACKAGED_BACKEND_CONFIG).toBeDefined()
    expect(constants.PACKAGED_BACKEND_CONFIG.executableName).toBe('comicstudio-backend')
    expect(constants.PACKAGED_BACKEND_CONFIG.host).toBe('127.0.0.1')
    expect(constants.PACKAGED_BACKEND_CONFIG.port).toBe(8000)
  })

  it('getPackagedBackendPath returns a string', async () => {
    const constants = await import('../main/constants')
    const p = constants.getPackagedBackendPath()
    expect(typeof p).toBe('string')
    expect(p.length).toBeGreaterThan(0)
  })

  it('getPackagedBackendPath respects env override', async () => {
    const orig = process.env.CS_PACKAGED_BACKEND_PATH
    process.env.CS_PACKAGED_BACKEND_PATH = '/test/path/backend.exe'
    try {
      const constants = await import('../main/constants')
      expect(constants.getPackagedBackendPath()).toBe('/test/path/backend.exe')
    } finally {
      if (orig === undefined) {
        delete process.env.CS_PACKAGED_BACKEND_PATH
      } else {
        process.env.CS_PACKAGED_BACKEND_PATH = orig
      }
    }
  })

  it('backend-process imports getPackagedBackendPath', async () => {
    const source = await import('fs').then(fs =>
      fs.promises.readFile(
        require('path').resolve(__dirname, '../main/backend/backend-process.ts'),
        'utf-8'
      )
    )
    expect(source).toContain('getPackagedBackendPath')
    expect(source).toContain('usePackaged')
  })

  it('electron-builder.yml includes extraResources for backend', async () => {
    const fs = await import('fs')
    const path = await import('path')
    const yamlPath = path.resolve(__dirname, '../../electron-builder.yml')
    const content = await fs.promises.readFile(yamlPath, 'utf-8')
    expect(content).toContain('extraResources')
    expect(content).toContain('comicstudio-backend')
  })
})
