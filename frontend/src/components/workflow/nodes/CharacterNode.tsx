import { Handle, Position } from 'reactflow'
import { UserOutlined } from '@ant-design/icons'

interface CharacterNodeData {
  label?: string
  name?: string
  style?: string
}

export default function CharacterNode({ data }: { data: CharacterNodeData }) {
  return (
    <div className="bg-[#2a2a3e] border border-[#313244] rounded-lg p-3 w-48 text-white">
      <Handle type="source" position={Position.Right} className="!bg-purple-500" />
      <div className="flex items-center gap-2 mb-2">
        <UserOutlined className="text-purple-400" />
        <span className="font-semibold text-sm">{data.label || '角色'}</span>
      </div>
      <div className="text-xs text-gray-400">名称: {data.name || '未命名'}</div>
      <div className="text-xs text-gray-400">风格: {data.style || 'anime'}</div>
    </div>
  )
}
