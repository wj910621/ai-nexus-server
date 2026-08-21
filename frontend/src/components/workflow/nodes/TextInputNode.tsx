import { Handle, Position, type NodeProps } from 'reactflow'

interface TextInputData {
  params?: { value?: string }
}

export default function TextInputNode({ data, selected }: NodeProps<TextInputData>) {
  return (
    <div className={`px-4 py-3 rounded-lg bg-[#2a2a3e] border-2 min-w-[180px] ${
      selected ? 'border-indigo-500' : 'border-[#313244]'
    }`}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">📝</span>
        <span className="text-sm font-medium text-white">文本输入</span>
      </div>
      <div className="text-xs text-gray-400 truncate">
        {data.params?.value || '(空)'}
      </div>
      <Handle
        type="source"
        position={Position.Right}
        id="text"
        className="!bg-emerald-500 !w-3 !h-3"
      />
    </div>
  )
}
