import { Handle, Position, type NodeProps } from 'reactflow'

interface TextConcatData {
  params?: { separator?: string }
}

export default function TextConcatNode({ data, selected }: NodeProps<TextConcatData>) {
  return (
    <div className={`px-4 py-3 rounded-lg bg-[#2a2a3e] border-2 min-w-[180px] ${
      selected ? 'border-indigo-500' : 'border-[#313244]'
    }`}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">🔗</span>
        <span className="text-sm font-medium text-white">文本拼接</span>
      </div>
      <div className="text-xs text-gray-400">
        分隔符: {data.params?.separator || ', '}
      </div>
      <Handle
        type="target"
        position={Position.Left}
        id="text1"
        className="!bg-indigo-500 !w-3 !h-3"
      />
      <Handle
        type="target"
        position={Position.Left}
        id="text2"
        style={{ top: '50%' }}
        className="!bg-indigo-500 !w-3 !h-3"
      />
      <Handle
        type="target"
        position={Position.Left}
        id="text3"
        style={{ top: '75%' }}
        className="!bg-indigo-500 !w-3 !h-3"
      />
      <Handle
        type="source"
        position={Position.Right}
        id="text"
        className="!bg-emerald-500 !w-3 !h-3"
      />
    </div>
  )
}
