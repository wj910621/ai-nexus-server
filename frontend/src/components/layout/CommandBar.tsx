/**
 * S1 底部命令栏（全局）：/ 指令提示 + 自然语言 + 模型选择（agentStore 全局一致）
 * 提交文本通过 onSend 交由上层（跳转 Agent 工作台并带入草稿）
 */
import { useRef, useState } from 'react'
import { Button, Input, Select, Tooltip, message } from 'antd'
import { PaperClipOutlined, SendOutlined } from '@ant-design/icons'
import { useAgentStore } from '@/stores/agentStore'

const MODELS = [
  { value: 'deepseek-chat', label: 'DeepSeek V3' },
  { value: 'qwen-plus', label: 'Qwen Plus' },
  { value: 'qwen-flash', label: 'Qwen Flash' },
  { value: 'kimi-k2', label: 'Kimi K2' },
]

const MAX_FILE_BYTES = 200_000

export default function CommandBar({ onSend }: { onSend?: (text: string) => void }) {
  const model = useAgentStore((s) => s.model)
  const setModel = useAgentStore((s) => s.setModel)
  const [text, setText] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const submit = () => {
    const v = text.trim()
    if (!v) return
    onSend?.(v)
    setText('')
  }

  const pickFile = () => {
    fileRef.current?.click()
  }

  const onFile = (ev: React.ChangeEvent<HTMLInputElement>) => {
    const file = ev.target.files?.[0]
    ev.target.value = ''
    if (!file) return
    if (file.size > MAX_FILE_BYTES) {
      void message.warning(`文件过大（>${Math.round(MAX_FILE_BYTES / 1024)}KB），暂仅支持文本/代码文件导入`)
      return
    }
    const reader = new FileReader()
    reader.onload = () => {
      const content = String(reader.result ?? '').slice(0, MAX_FILE_BYTES)
      setText((prev) => `${prev.trim() ? prev.trim() + '\n' : ''}[文件: ${file.name}]\n${content}`)
      void message.success(`已载入 ${file.name}`)
    }
    reader.onerror = () => void message.error('文件读取失败')
    reader.readAsText(file)
  }

  return (
    <div className="border-t border-[#313244] bg-[#1e1e2e] px-4 py-2 flex items-end gap-2">
      <input ref={fileRef} type="file" hidden onChange={onFile} />
      <Tooltip title="载入文件/文本（≤200KB）">
        <Button shape="circle" icon={<PaperClipOutlined />} aria-label="上传" onClick={pickFile} />
      </Tooltip>
      <Input.TextArea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onPressEnter={(e) => {
          if (!e.shiftKey) {
            e.preventDefault()
            submit()
          }
        }}
        autoSize={{ minRows: 1, maxRows: 5 }}
        placeholder="输入指令（/ 查看快捷命令），Enter 发送，Shift+Enter 换行"
        className="!bg-[#11111b] !text-gray-100 !border-[#313244] flex-1"
      />
      <Select value={model} onChange={setModel} options={MODELS} size="small" className="w-36" popupMatchSelectWidth={false} />
      <Button type="primary" icon={<SendOutlined />} onClick={submit} aria-label="发送" />
    </div>
  )
}
