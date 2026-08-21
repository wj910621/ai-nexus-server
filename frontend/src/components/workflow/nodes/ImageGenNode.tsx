import { Handle, Position } from 'reactflow'
import { PictureOutlined } from '@ant-design/icons'

interface ImageGenNodeData {
  label?: string
  model?: string
  prompt?: string
}

export default function ImageGenNode({ data }: { data: ImageGenNodeData }) {
  return (
    <div className="bg-[#2a2a3e] border border-[#313244] rounded-lg p-3 w-56 text-white">
      <Handle type="target" position={Position.Left} className="!bg-blue-500" />
      <div className="flex items-center gap-2 mb-2">
        <PictureOutlined className="text-blue-400" />
        <span className="font-semibold text-sm">{data.label || '图像生成'}</span>
      </div>
      <div className="text-xs text-gray-400 mb-1">模型: {data.model || 'SDXL'}</div>
      <div className="text-xs text-gray-300 truncate">
        {data.prompt || '请输入提示词...'}
      </div>
      <Handle type="source" position={Position.Right} className="!bg-green-500" />
    </div>
  )
}
