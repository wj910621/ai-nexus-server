import { Handle, Position, type NodeProps } from 'reactflow'

interface TTSData {
  params?: { voice?: string; rate?: number; pitch?: number }
}

export default function TTSNode({ data, selected }: NodeProps<TTSData>) {
  return (
    <div className={`px-4 py-3 rounded-lg bg-[#2a2a3e] border-2 min-w-[180px] ${
      selected ? 'border-indigo-500' : 'border-[#313244]'
    }`}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">🔊</span>
        <span className="text-sm font-medium text-white">语音合成</span>
      </div>
      <div className="text-xs text-gray-400">
        {data.params?.voice || 'zh-CN-XiaoxiaoNeural'}
      </div>
      <Handle
        type="target"
        position={Position.Left}
        id="text"
        className="!bg-indigo-500 !w-3 !h-3"
      />
      <Handle
        type="source"
        position={Position.Right}
        id="audio"
        className="!bg-emerald-500 !w-3 !h-3"
      />
    </div>
  )
}
