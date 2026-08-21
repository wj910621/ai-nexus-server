import { describe, it, expect } from 'vitest'
import { IPC_CHANNELS } from '@shared/ipc-channels'
import { IPC_PREFIX } from '@main/constants'

describe('IPC_CHANNELS', () => {
  it('all channels start with the IPC_PREFIX', () => {
    for (const [key, channel] of Object.entries(IPC_CHANNELS)) {
      expect(channel).toMatch(new RegExp(`^${IPC_PREFIX}`))
    }
  })

  it('all channels are unique', () => {
    const values = Object.values(IPC_CHANNELS)
    const unique = new Set(values)
    expect(unique.size).toBe(values.length)
  })

  it('app channels follow naming pattern', () => {
    expect(IPC_CHANNELS.APP_GET_VERSION).toBe(`${IPC_PREFIX}app:getVersion`)
    expect(IPC_CHANNELS.APP_GET_PLATFORM).toBe(`${IPC_PREFIX}app:getPlatform`)
  })

  it('window channels cover all controls', () => {
    const windowChannels = Object.entries(IPC_CHANNELS)
      .filter(([k]) => k.startsWith('WINDOW_'))
      .map(([, v]) => v)
    // 7 window channels: minimize, maximize, unmaximize, close, isMaximized, toggleMaximize, stateChange
    expect(windowChannels.length).toBeGreaterThanOrEqual(7)
  })

  it('fs channels cover core operations', () => {
    const fsChannels = Object.entries(IPC_CHANNELS)
      .filter(([k]) => k.startsWith('FS_'))
      .map(([, v]) => v)
    expect(fsChannels.length).toBeGreaterThanOrEqual(5)
  })

  it('shell channels include openExternal', () => {
    expect(IPC_CHANNELS.SHELL_OPEN_EXTERNAL).toContain('openExternal')
  })

  it('clipboard has read and write', () => {
    expect(IPC_CHANNELS.CLIPBOARD_READ_TEXT).toContain('readText')
    expect(IPC_CHANNELS.CLIPBOARD_WRITE_TEXT).toContain('writeText')
  })

  it('navigate channel exists for main->renderer', () => {
    expect(IPC_CHANNELS.NAVIGATE).toBeDefined()
  })
})
