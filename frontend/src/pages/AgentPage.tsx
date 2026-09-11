/**
 * S1 创作智能 Agent 面板（store 驱动 + CommandBar 全局流转）
 *  - 会话列表/新建/清空/删除 + 消息持久化（agentStore）
 *  - 桌面端主站账号直连（electronAPI.agent）；浏览器环境降级提示
 *  - R2: 对话自动写入本地记忆库 + 跨会话记忆检索
 *  - R3: 资产库云端同步（拉取/上传/删除联动）
 */
import { useEffect, useRef, useState } from 'react'
import { Button, Empty, Input, Select, Spin, Tag, Tooltip, Typography, message } from 'antd'
import {
  RobotOutlined, SendOutlined, ExportOutlined, PlusOutlined,
  ClearOutlined, DeleteOutlined,
} from '@ant-design/icons'
import { isDesktop } from '@/utils/mainAccount'
import { useAgentStore } from '@/stores/agentStore'
import type { AgentMessage } from '@/api/agent'
import { useAssetStore, parseTitleFromScript } from '@/stores/assetStore'
import { SaveOutlined, CopyOutlined, SearchOutlined, SyncOutlined, CloudOutlined } from '@ant-design/icons'
import type { MemoryRecord } from '@/utils/runtime'

const MODELS = [
  { value: 'deepseek-chat', label: 'DeepSeek V3' },
  { value: 'qwen-plus', label: 'Qwen Plus' },
  { value: 'qwen-flash', label: 'Qwen Flash' },
  { value: 'kimi-k2', label: 'Kimi K2' },
]
const GENRES = ['古风', '科幻', '都市', '悬疑']

/** R2: 记忆写入（fire-and-forget，桌面端可用；失败静默不影响对话） */
function recordMemory(sessionId: string, role: 'user' | 'assistant', content: string) {
  try {
    const p = window.electronAPI?.memory?.append(sessionId, role, content)
    if (p && typeof p.catch === 'function') p.catch(() => undefined)
  } catch {
    /* 记忆桥不可用：忽略 */
  }
}

export default function AgentPage() {
  const {
    sessions, currentSessionId, model, busy, draft,
    setModel, setBusy, setDraft, setError, appendMessage,
    newSession, openSession, clearCurrent, removeSession,
  } = useAgentStore()

  const [premise, setPremise] = useState('')
  const [genre, setGenre] = useState(GENRES[0])
  const [script, setScript] = useState('')
  const [localInput, setLocalInput] = useState('')
  const [memKeyword, setMemKeyword] = useState('')
  const [memResults, setMemResults] = useState<MemoryRecord[]>([])
  const [memBusy, setMemBusy] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const { assets, addAsset } = useAssetStore()
  const syncStatus = useAssetStore((s) => s.syncStatus)
  const syncMessage = useAssetStore((s) => s.syncMessage)
  const lastSyncAt = useAssetStore((s) => s.lastSyncAt)

  const cur = sessions.find((s) => s.id === currentSessionId) ?? null
  const messages: AgentMessage[] = cur?.messages ?? []
  const input = draft && cur === null ? draft : localInput

  // CommandBar 草稿订阅：任何时刻 draft 到达 → 自动开新会话并置入输入
  useEffect(() => {
    if (!draft) return
    if (!useAgentStore.getState().currentSessionId) newSession()
    setLocalInput(draft)
    useAgentStore.getState().setDraft('')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, busy])

  const chat = async (text: string) => {
    const v = text.trim()
    if (!v || busy) return
    if (!isDesktop()) {
      void message.warning('请在桌面端使用主站账号登录后体验（当前为浏览器预览）')
      return
    }
    const api = window.electronAPI?.agent
    if (!api) {
      void message.warning('Agent 桥不可用（桌面端 preload 未就绪）')
      return
    }
    appendMessage({ role: 'user', content: v })
    setLocalInput('')
    setBusy(true)
    setError(null)
    const sid = useAgentStore.getState().currentSessionId ?? 'default'
    recordMemory(sid, 'user', v)
    try {
      const history = useAgentStore.getState().sessions.find((s) => s.id === useAgentStore.getState().currentSessionId)?.messages ?? []
      const r = (await api.chat([...history.slice(-12)], model)) as
        | { ok: true; content: string }
        | { ok: false; code: string; message: string }
      if (!r.ok) throw new Error((r as { message: string }).message || '调用失败')
      const answer = (r as { content: string }).content
      appendMessage({ role: 'assistant', content: answer })
      recordMemory(sid, 'assistant', answer)
    } catch (err) {
      setError((err as Error).message)
      appendMessage({ role: 'assistant', content: `⚠️ ${(err as Error).message}` })
    } finally {
      setBusy(false)
    }
  }

  const genScript = async () => {
    if (!isDesktop()) {
      void message.warning('请在桌面端使用主站账号登录后体验')
      return
    }
    if (!premise.trim()) {
      void message.info('请先输入一句话故事梗概')
      return
    }
    const api = window.electronAPI?.agent
    if (!api) return
    setBusy(true)
    setScript('')
    try {
      const r = (await api.createComicScript(premise.trim(), genre)) as
        | { ok: true; content: string }
        | { ok: false; code: string; message: string }
      if (!r.ok) throw new Error((r as { message: string }).message || '生成失败')
      const content = (r as { content: string }).content
      setScript(content)
      appendMessage({ role: 'assistant', content: `已生成「${genre}」题材漫剧脚本（${content.length} 字符）` })
      recordMemory(useAgentStore.getState().currentSessionId ?? 'default', 'assistant', `[漫剧脚本/${genre}] ${premise.trim()}`)
    } catch (err) {
      void message.error((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const exportScript = () => {
    if (!script) return
    const blob = new Blob([script], { type: 'application/json;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `comic-script-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
    void message.success('已导出分镜脚本 JSON')
  }

  const saveScript = () => {
    if (!script) return
    const title = parseTitleFromScript(script)
    addAsset({ kind: 'comic-script', title, genre, premise: premise.trim(), content: script })
    void message.success(`已存入资产库：${title}（可点"同步云端"上传）`)
  }

  const copyScript = (content: string) => {
    void navigator.clipboard?.writeText(content)
    void message.success('已复制到剪贴板')
  }

  /** R3: 资产库云端同步（拉取 + 上传未入云条目） */
  const syncAssets = async () => {
    const r = await useAssetStore.getState().syncNow()
    if (r.ok) void message.success(`同步完成：拉取 ${r.pulled} · 上传 ${r.pushed}`)
    else void message.warning(`同步未完全成功（失败 ${r.failed}）：${r.message ?? '请检查主站登录状态'}`)
  }

  /** R3: 删除资产（本地 + 云端） */
  const removeAssetDeep = async (id: string) => {
    const r = await useAssetStore.getState().removeAssetDeep(id)
    if (!r.ok) void message.warning(`本地已删除，云端删除失败：${r.message ?? '未知原因'}`)
  }

  /** R2: 跨会话记忆检索 */
  const searchMemory = async () => {
    const api = window.electronAPI?.memory
    if (!api) {
      void message.warning('记忆桥不可用（桌面端 preload 未就绪）')
      return
    }
    setMemBusy(true)
    try {
      const r = (await api.search(memKeyword.trim(), 20)) as { records?: MemoryRecord[] }
      const records = r?.records ?? []
      setMemResults(records)
      if (records.length === 0) void message.info('未检索到相关记忆')
    } catch (err) {
      void message.error((err as Error).message)
    } finally {
      setMemBusy(false)
    }
  }

  const pending = assets.filter((a) => !a.cloudId).length

  return (
    <div className="flex h-full">
      {/* 左：会话列表 */}
      <div className="w-52 border-r border-[#313244] flex flex-col bg-[#1e1e2e]">
        <div className="p-2 border-b border-[#313244]">
          <Button size="small" type="primary" block icon={<PlusOutlined />} onClick={newSession}>
            新会话
          </Button>
        </div>
        <div className="flex-1 overflow-auto p-2 space-y-1">
          {sessions.length === 0 && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={<span className="text-xs text-gray-500">暂无会话</span>} />}
          {sessions.map((s) => (
            <div
              key={s.id}
              className={`group rounded px-2 py-1.5 text-xs cursor-pointer flex items-center justify-between ${s.id === currentSessionId ? 'bg-[#3b3f54] text-white' : 'text-gray-400 hover:bg-[#2a2a3e]'}`}
              onClick={() => openSession(s.id)}
            >
              <span className="truncate">{s.title}</span>
              <span
                className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400"
                onClick={(e) => {
                  e.stopPropagation()
                  removeSession(s.id)
                }}
              >
                <DeleteOutlined style={{ fontSize: 11 }} />
              </span>
            </div>
          ))}
        </div>
        {cur && (
          <div className="p-2 border-t border-[#313244]">
            <Button size="small" ghost icon={<ClearOutlined />} onClick={clearCurrent} className="!text-gray-400">
              清空当前
            </Button>
          </div>
        )}
      </div>

      {/* 中：对话主区 */}
      <div className="flex-1 flex flex-col">
        <div className="px-4 py-2 border-b border-[#313244] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <RobotOutlined style={{ color: '#60a5fa' }} />
            <Typography.Text className="!text-white !text-sm">创作智能 Agent</Typography.Text>
            <Tag color="processing" style={{ fontSize: 10 }}>
              {isDesktop() ? '主站账号直连' : '浏览器预览'}
            </Tag>
          </div>
          <Select size="small" value={model} onChange={setModel} options={MODELS} style={{ width: 150 }} />
        </div>

        <div className="flex-1 overflow-auto px-4 py-3 space-y-3">
          {messages.map((m, i) => (
            <div key={i} className={m.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
              <div
                className={`max-w-[78%] rounded-lg px-3 py-2 whitespace-pre-wrap text-sm ${
                  m.role === 'user' ? 'bg-blue-600 text-white' : 'bg-[#313244] text-gray-100'
                }`}
              >
                {m.content}
              </div>
            </div>
          ))}
          {busy && (
            <div className="flex items-center gap-2 text-gray-400 text-xs">
              <Spin size="small" /> Agent 思考中…
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="border-t border-[#313244] px-4 py-2 space-y-2">
          {/* 漫剧脚本生成区 */}
          <div className="flex items-center gap-2">
            <Input
              placeholder="故事梗概（一句话）…"
              value={premise}
              onChange={(e) => setPremise(e.target.value)}
              className="!bg-[#11111b] !text-gray-100 !border-[#313244] flex-1"
              size="small"
            />
            <Select size="small" value={genre} onChange={setGenre} options={GENRES.map((g) => ({ value: g, label: g }))} style={{ width: 90 }} />
            <Button size="small" type="primary" ghost icon={<RobotOutlined />} loading={busy} onClick={genScript}>
              生成漫剧脚本
            </Button>
            {script && (
              <>
                <Button size="small" icon={<SaveOutlined />} onClick={saveScript}>
                  存入资产库
                </Button>
                <Button size="small" icon={<ExportOutlined />} onClick={exportScript}>
                  导出 JSON
                </Button>
              </>
            )}
          </div>
          {script && (
            <pre className="max-h-36 overflow-auto rounded bg-[#11111b] border border-[#313244] text-[11px] text-emerald-300 p-2">
              {script}
            </pre>
          )}

          {/* R2: 记忆检索 */}
          <div className="border-t border-[#313244] pt-2">
            <div className="flex items-center gap-2">
              <SearchOutlined style={{ color: '#6b7280', fontSize: 12 }} />
              <Input
                size="small"
                placeholder="检索跨会话记忆（关键词）…"
                value={memKeyword}
                onChange={(e) => setMemKeyword(e.target.value)}
                onPressEnter={() => void searchMemory()}
                className="!bg-[#11111b] !text-gray-100 !border-[#313244] flex-1"
              />
              <Button size="small" loading={memBusy} onClick={() => void searchMemory()}>
                检索
              </Button>
              {memResults.length > 0 && (
                <Button size="small" type="text" className="!text-gray-500" onClick={() => setMemResults([])}>
                  清空
                </Button>
              )}
            </div>
            {memResults.length > 0 && (
              <div className="mt-1 flex flex-col gap-1 max-h-32 overflow-auto">
                {memResults.map((m, i) => (
                  <div key={i} className="text-[11px] bg-[#11111b] rounded px-2 py-1 flex gap-2">
                    <Tag color={m.role === 'user' ? 'blue' : 'default'} style={{ fontSize: 9, marginRight: 0 }}>
                      {m.role === 'user' ? '我' : 'AI'}
                    </Tag>
                    <span className="text-gray-300 truncate flex-1">{m.content}</span>
                    <span className="text-gray-600 shrink-0">{m.ts ? new Date(m.ts).toLocaleDateString('zh-CN') : ''}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* R3: 资产库（本地 + 云端同步） */}
          <div className="border-t border-[#313244] pt-2">
            <div className="flex items-center justify-between mb-1">
              <div className="text-[11px] text-gray-500 flex items-center gap-2">
                <span>资产库（本地 {assets.length} 条{pending > 0 ? ` · 待同步 ${pending}` : ''}）</span>
                {lastSyncAt && (
                  <span className="text-gray-600">上次同步 {new Date(lastSyncAt).toLocaleTimeString('zh-CN')}</span>
                )}
                {syncStatus === 'error' && syncMessage && (
                  <Tooltip title={syncMessage}>
                    <Tag color="error" style={{ fontSize: 9 }}>同步异常</Tag>
                  </Tooltip>
                )}
                {syncStatus === 'offline' && <Tag color="default" style={{ fontSize: 9 }}>未登录主站</Tag>}
              </div>
              <Button
                size="small"
                type="text"
                icon={<CloudOutlined />}
                loading={syncStatus === 'syncing'}
                className="!text-gray-400"
                onClick={() => void syncAssets()}
                disabled={assets.length === 0}
              >
                同步云端
              </Button>
            </div>
            {assets.length === 0 ? (
              <div className="text-[11px] text-gray-600">暂无资产，生成脚本后点击"存入资产库"</div>
            ) : (
              <div className="flex flex-col gap-1 max-h-40 overflow-auto">
                {assets.map((a) => (
                  <div key={a.id} className="flex items-center gap-2 text-xs bg-[#11111b] rounded px-2 py-1">
                    <span className="text-gray-300 truncate flex-1">
                      {a.title}
                      <span className="text-gray-500"> · {a.genre} · {a.premise.slice(0, 20) || '无梗概'}</span>
                    </span>
                    {a.cloudId ? (
                      <Tag color="blue" style={{ fontSize: 9, marginRight: 0 }}>云#{a.cloudId}</Tag>
                    ) : (
                      <Tag style={{ fontSize: 9, marginRight: 0 }}>本地</Tag>
                    )}
                    <Button size="small" type="text" icon={<CopyOutlined />} onClick={() => copyScript(a.content)} />
                    <Button size="small" type="text" danger onClick={() => void removeAssetDeep(a.id)}>
                      删
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 对话输入 */}
          <div className="flex gap-2">
            <Input.TextArea
              value={input}
              onChange={(e) => setLocalInput(e.target.value)}
              onPressEnter={(e) => {
                if (!e.shiftKey) {
                  e.preventDefault()
                  void chat(input)
                }
              }}
              autoSize={{ minRows: 1, maxRows: 4 }}
              placeholder="输入问题，Enter 发送；上方可一键生成漫剧分镜…"
              className="!bg-[#11111b] !text-gray-100 !border-[#313244]"
            />
            <Button type="primary" icon={<SendOutlined />} loading={busy} onClick={() => void chat(input)} />
          </div>
        </div>
      </div>
    </div>
  )
}
