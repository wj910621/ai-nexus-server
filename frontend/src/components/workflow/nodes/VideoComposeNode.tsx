import { Handle, Position, type NodeProps } from 'reactflow'

interface VideoComposeData {
  params?: { fps?: number; width?: number; height?: number }
}

export default function VideoComposeNode({ data, selected }: NodeProps<VideoComposeData>) {
  return (
    <div className={`px-4 py-3 rounded-lg bg-[#2a2a3e] border-2 min-w-[180px] ${
      selected ? 'border-indigo-500' : 'border-[#313244]'
    }`}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">🎬</span>
        <span className="text-sm font-medium text-white">视频合成</span>
      </div>
      <div className="text-xs text-gray-400">
        {data.params?.width || 1920}×{data.params?.height || 1080} @ {data.params?.fps || 24}fps
      </div>
      <Handle
        type="target"
        position={Position.Left}
        id="frames"
        className="!bg-indigo-500 !w-3 !h-3"
      />
      <Handle
        type="target"
        position={Position.Left}
        id="audio"
        style={{ top: '70%' }}
        className="!bg-indigo-500 !w-3 !h-3"
      />
      <Handle
        type="source"
        position={Position.Right}
        id="video"
        className="!bg-emerald-500 !w-3 !h-3"
      />
    </div>
  )
}
