import { Handle, Position, type NodeProps } from 'reactflow'

interface LLMChatData {
  params?: {
    model?: string
    temperature?: number
    max_tokens?: number
  }
}

export default function LLMChatNode({ data, selected }: NodeProps<LLMChatData>) {
  return (
    <div className={`px-4 py-3 rounded-lg bg-[#2a2a3e] border-2 min-w-[180px] ${
      selected ? 'border-indigo-500' : 'border-[#313244]'
    }`}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">💬</span>
        <span className="text-sm font-medium text-white">LLM 对话</span>
      </div>
      <div className="text-xs text-gray-400">
        模型: {data.params?.model || 'deepseek-chat'}
      </div>
      <Handle
        type="target"
        position={Position.Left}
        id="user_message"
        className="!bg-indigo-500 !w-3 !h-3"
      />
      <Handle
        type="target"
        position={Position.Left}
        id="system_prompt"
        style={{ top: '70%' }}
        className="!bg-indigo-500 !w-3 !h-3"
      />
      <Handle
        type="source"
        position={Position.Right}
        id="response"
        className="!bg-emerald-500 !w-3 !h-3"
      />
    </div>
  )
}
