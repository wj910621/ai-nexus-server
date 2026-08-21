import { describe, it, expect } from 'vitest'
import {
  APP_NAME,
  APP_VERSION,
  WINDOW_DEFAULTS,
  DEV_SERVER_URL,
  PROD_RENDERER_ENTRY,
  BACKEND_URL,
  IPC_PREFIX,
} from '@main/constants'

describe('constants', () => {
  it('APP_NAME is a non-empty string', () => {
    expect(typeof APP_NAME).toBe('string')
    expect(APP_NAME.length).toBeGreaterThan(0)
  })

  it('APP_VERSION matches semver-like pattern', () => {
    expect(APP_VERSION).toMatch(/^\d+\.\d+\.\d+/)
  })

  it('WINDOW_DEFAULTS has required fields with sane values', () => {
    expect(WINDOW_DEFAULTS.width).toBeGreaterThanOrEqual(WINDOW_DEFAULTS.minWidth)
    expect(WINDOW_DEFAULTS.height).toBeGreaterThanOrEqual(WINDOW_DEFAULTS.minHeight)
    expect(WINDOW_DEFAULTS.minWidth).toBeGreaterThanOrEqual(800)
    expect(WINDOW_DEFAULTS.minHeight).toBeGreaterThanOrEqual(600)
  })

  it('DEV_SERVER_URL is a valid http URL', () => {
    expect(DEV_SERVER_URL).toMatch(/^http:\/\/localhost:\d+$/)
  })

  it('PROD_RENDERER_ENTRY points to index.html', () => {
    expect(PROD_RENDERER_ENTRY).toContain('index.html')
  })

  it('BACKEND_URL is defined', () => {
    expect(BACKEND_URL).toBeTruthy()
  })

  it('IPC_PREFIX is a non-empty string ending with colon', () => {
    expect(IPC_PREFIX).toMatch(/^.+:$/)
  })
})
