/**
 * S1 Agent 工作台全局状态（zustand + persist）
 *  - 对话消息/模型/busy/draft 全应用共享：CommandBar 提交 → draft 入 store → 路由到 /agent
 *  - 会话持久化（localStorage 上限 200 条/会话，避免无限增长）
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { AgentMessage } from '@/api/agent'

const DEFAULT_WELCOME: AgentMessage = {
  role: 'assistant',
  content:
    '我是创作智能 Agent。可以直接聊天，也可以把一句话梗概扩写成漫剧分镜脚本（Agent 页"生成漫剧脚本"）。',
}

export interface Session {
  id: string
  title: string
  messages: AgentMessage[]
  createdAt: number
}

interface AgentStoreState {
  model: string
  busy: boolean
  draft: string
  currentSessionId: string | null
  sessions: Session[]
  lastError: string | null
  setModel: (m: string) => void
  setBusy: (b: boolean) => void
  setDraft: (d: string) => void
  appendMessage: (m: AgentMessage) => void
  newSession: () => void
  openSession: (id: string) => void
  clearCurrent: () => void
  removeSession: (id: string) => void
  setError: (e: string | null) => void
}

function freshSession(): Session {
  return { id: `s_${Date.now()}`, title: '新会话', messages: [DEFAULT_WELCOME], createdAt: Date.now() }
}

const LIMIT_MESSAGES = 200
const LIMIT_SESSIONS = 50

function trimSession(s: Session): Session {
  if (s.messages.length > LIMIT_MESSAGES) {
    return { ...s, messages: s.messages.slice(-LIMIT_MESSAGES) }
  }
  return s
}

export const useAgentStore = create<AgentStoreState>()(
  persist(
    (set, get) => ({
      model: 'deepseek-chat',
      busy: false,
      draft: '',
      currentSessionId: null,
      sessions: [],
      lastError: null,

      setModel: (m) => set({ model: m }),
      setBusy: (b) => set({ busy: b }),
      setDraft: (d) => set({ draft: d }),
      setError: (e) => set({ lastError: e }),

      appendMessage: (m) => {
        const { currentSessionId, sessions } = get()
        let id = currentSessionId
        let list = sessions
        if (!id) {
          id = freshSession().id
          list = [{ ...freshSession(), id }, ...list]
        }
        const next = list.map((s) =>
          s.id === id
            ? trimSession({ ...s, messages: [...s.messages, m], title: s.messages.length <= 1 ? m.content.slice(0, 24) : s.title })
            : s
        )
        set({ sessions: next.slice(0, LIMIT_SESSIONS), currentSessionId: id })
      },

      newSession: () => {
        const s = freshSession()
        set((st) => ({ sessions: [s, ...st.sessions].slice(0, LIMIT_SESSIONS), currentSessionId: s.id }))
      },

      openSession: (id) => {
        if (!get().sessions.some((s) => s.id === id)) return
        set({ currentSessionId: id })
      },

      clearCurrent: () => {
        const { currentSessionId, sessions } = get()
        if (!currentSessionId) return
        set({ sessions: sessions.map((s) => (s.id === currentSessionId ? { ...freshSession(), id: s.id } : s)) })
      },

      removeSession: (id) => {
        const { sessions, currentSessionId } = get()
        const next = sessions.filter((s) => s.id !== id)
        set({ sessions: next, currentSessionId: currentSessionId === id ? null : currentSessionId })
      },
    }),
    { name: 'yn.agent.sessions' }
  )
)
