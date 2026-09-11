/**
 * R2 记忆系统 — IPC handlers（username 取自主站 token，缺省 anonymous）
 */
import { ipcMain } from 'electron'
import { IPC_CHANNELS } from '@shared/ipc-channels'
import { app } from 'electron'
import path from 'path'
import { MemoryService } from '../services/memory-service'
import type { AccountStoreLike } from '../services/account-service'

let svc: MemoryService | null = null

function service(): MemoryService {
  if (!svc) {
    const dir = path.join(app.getPath('userData'), 'memory')
    svc = new MemoryService(dir)
  }
  return svc
}

function currentUser(): string {
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const mod = require('electron-store') as { default?: unknown }
    const Ctor = (mod?.default ?? mod) as new (o?: { name?: string }) => AccountStoreLike
    const store = new Ctor({ name: 'account' })
    const u = store.get('username')
    return typeof u === 'string' && u ? u : 'anonymous'
  } catch {
    return 'anonymous'
  }
}

export function registerMemoryHandlers(): void {
  ipcMain.handle(IPC_CHANNELS.MEMORY_APPEND, (_e, args: { sessionId?: string; role?: string; content?: string }) => {
    const role = args?.role === 'user' || args?.role === 'assistant' || args?.role === 'system' ? args.role : 'system'
    service().append({ username: currentUser(), sessionId: String(args?.sessionId || 'default'), role, content: String(args?.content || '') })
    return { ok: true }
  })
  ipcMain.handle(IPC_CHANNELS.MEMORY_SEARCH, (_e, args: { keyword?: string; limit?: number }) => {
    return service().query(currentUser(), String(args?.keyword || ''), Math.min(Number(args?.limit) || 50, 200))
  })
  ipcMain.handle(IPC_CHANNELS.MEMORY_RECENT, async (_e, args: { limit?: number }) => {
    return { records: service().recent(currentUser(), Math.min(Number(args?.limit) || 30, 100)) }
  })
}
