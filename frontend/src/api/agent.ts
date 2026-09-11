/**
 * P4 Agent 前端类型桥
 * 桌面端经 window.electronAPI.agent（主进程 AgentService → 主站网关）
 * 浏览器环境无 electronAPI 时组件降级提示（不发起请求）。
 */
export interface AgentMessage {
  role: 'system' | 'user' | 'assistant'
  content: string
}

export type AgentChatResult =
  | { ok: true; content: string; model: string }
  | { ok: false; code: 'unauthorized' | 'network' | 'invalid' | 'quota'; message: string }

export function desktopAgentAvailable(): boolean {
  return typeof window !== 'undefined' && !!window.electronAPI?.agent
}

export async function desktopAgentChat(messages: AgentMessage[], model: string): Promise<AgentChatResult> {
  const api = window.electronAPI?.agent
  if (!api) return { ok: false, code: 'invalid', message: '桌面 Agent 桥不可用' }
  const r = (await api.chat(messages, model)) as AgentChatResult
  return r
}
