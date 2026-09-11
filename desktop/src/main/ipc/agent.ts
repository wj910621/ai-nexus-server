/**
 * P3 创作智能层 —— Agent IPC handlers
 */
import { ipcMain } from 'electron'
import { IPC_CHANNELS } from '@shared/ipc-channels'
import { AgentService, type AgentMessage } from '../services/agent-service'
import type { AccountStoreLike } from '../services/account-service'

let agent: AgentService | null = null

function service(): AgentService {
  if (!agent) {
    const apiBase = process.env.YNEX_API_BASE || 'https://ynexai.cn'
    let store: AccountStoreLike | null = null
    try {
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const mod = require('electron-store') as { default?: unknown }
      const Ctor = (mod?.default ?? mod) as new (o?: { name?: string }) => AccountStoreLike
      store = new Ctor({ name: 'account' })
    } catch {
      store = null
    }
    agent = new AgentService(
      () => {
        try {
          const t = store?.get('token')
          return typeof t === 'string' ? t : null
        } catch {
          return null
        }
      },
      apiBase,
    )
  }
  return agent
}

export function registerAgentHandlers(): void {
  ipcMain.handle(IPC_CHANNELS.AGENT_CHAT, async (_e, args: { messages: AgentMessage[]; model: string }) => {
    if (!args || !Array.isArray(args.messages)) return { ok: false, code: 'invalid', message: '参数错误' }
    return service().chat(args.messages.slice(0, 50), { model: String(args.model || 'deepseek-chat') })
  })
  ipcMain.handle(IPC_CHANNELS.AGENT_COMIC_SCRIPT, async (_e, args: { premise?: string; genre?: string }) => {
    return service().createComicScript(String(args?.premise ?? ''), String(args?.genre ?? '通用'))
  })
}
