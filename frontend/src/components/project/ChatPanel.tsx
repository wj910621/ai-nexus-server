import { useEffect, useState } from 'react'
import { Input, Button, Typography } from 'antd'
import { Send, Square, Sparkles } from 'lucide-react'
import { useSSE } from '@/hooks/useSSE'

const { Text } = Typography
const { TextArea } = Input

interface Message {
  role: 'user' | 'assistant'
  content: string
}

export default function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const { data, done, error, start, abort } = useSSE('/api/v1/chat?stream=true')

  const handleSend = () => {
    if (!input.trim()) return
    const userMessage: Message = { role: 'user', content: input }
    setMessages((prev) => [...prev, userMessage, { role: 'assistant', content: '' }])
    setIsStreaming(true)
    start()
    setInput('')
  }

  const handleAbort = () => {
    abort()
    setIsStreaming(false)
  }

  // SSE 数据是累积的（useSSE 内部 setData((prev) => prev + chunk)），
  // 因此直接用 data 替换最新 AI 消息内容，而不是累加，避免重复。
  useEffect(() => {
    if (data) {
      setMessages((prev) => {
        const last = prev[prev.length - 1]
        if (last?.role === 'assistant') {
          return [...prev.slice(0, -1), { ...last, content: data }]
        }
        return prev
      })
    }
  }, [data])

  // 流式结束/出错时重置 isStreaming
  useEffect(() => {
    if (done || error) {
      setIsStreaming(false)
    }
  }, [done, error])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--bg-surface)' }}>
      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-default)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <Sparkles size={16} style={{ color: 'var(--accent-cyan)' }} />
        <Text strong>AI 助手</Text>
      </div>

      <div style={{ flex: 1, padding: 16, overflowY: 'auto' }}>
        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              marginBottom: 12,
              padding: '10px 14px',
              borderRadius: 12,
              maxWidth: '85%',
              background: msg.role === 'user' ? 'var(--brand-primary)' : 'var(--bg-elevated)',
              color: msg.role === 'user' ? 'white' : 'var(--text-primary)',
              alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
              marginLeft: msg.role === 'user' ? 'auto' : 0,
              border: msg.role === 'assistant' ? '1px solid var(--border-default)' : 'none',
            }}
          >
            {msg.content}
            {msg.role === 'assistant' && isStreaming && i === messages.length - 1 && (
              <span style={{ display: 'inline-block', width: 2, height: 14, background: 'var(--accent-cyan)', marginLeft: 2, animation: 'blink 1s infinite', verticalAlign: 'text-bottom' }} />
            )}
          </div>
        ))}
        {error && (
          <div style={{ color: 'var(--accent-rose)', fontSize: 12, marginTop: 8 }}>
            [错误: {error.message}]
          </div>
        )}
      </div>

      <div style={{ padding: 12, borderTop: '1px solid var(--border-default)' }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
          <TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="输入消息，或描述你想要的内容..."
            autoSize={{ minRows: 1, maxRows: 4 }}
            disabled={isStreaming}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
          />
          {isStreaming ? (
            <Button danger onClick={handleAbort} icon={<Square size={14} />}>停止</Button>
          ) : (
            <Button type="primary" onClick={handleSend} icon={<Send size={14} />} disabled={!input.trim()}>
              发送
            </Button>
          )}
        </div>
        {isStreaming && (
          <Text type="secondary" style={{ fontSize: 11 }}>
            📡 SSE 流式中 · {data.length} chars
          </Text>
        )}
      </div>
    </div>
  )
}
