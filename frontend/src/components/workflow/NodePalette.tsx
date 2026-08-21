import { useEffect, useState } from 'react'
import { workflowEngineApi } from '@/api/workflows'
import { useEditorStore } from '@/stores/editorStore'
import type { NodeDefinition } from '@/types'

const CATEGORY_LABELS: Record<string, string> = {
  input: '输入',
  generation: '生成',
  processing: '处理',
  composite: '合成',
  output: '输出',
  utility: '工具',
}

const CATEGORY_COLORS: Record<string, string> = {
  input: 'bg-blue-500',
  generation: 'bg-purple-500',
  processing: 'bg-yellow-500',
  composite: 'bg-orange-500',
  output: 'bg-emerald-500',
  utility: 'bg-gray-500',
}

export default function NodePalette() {
  const [nodes, setNodes] = useState<NodeDefinition[]>([])
  const [loading, setLoading] = useState(true)
  const addNode = useEditorStore((s) => s.addNode)

  useEffect(() => {
    loadNodes()
  }, [])

  const loadNodes = async () => {
    try {
      const res = await workflowEngineApi.listNodes()
      setNodes(res.data.data)
    } catch (e) {
      console.error('加载节点失败', e)
    } finally {
      setLoading(false)
    }
  }

  const handleAddNode = (def: NodeDefinition) => {
    const id = `${def.type}_${Date.now()}`
    const newNode = {
      id,
      type: def.type,
      position: {
        x: 100 + Math.random() * 200,
        y: 100 + Math.random() * 200,
      },
      data: { params: {} },
    }
    addNode(newNode)
  }

  // 按分类分组
  const grouped = nodes.reduce((acc, n) => {
    if (!acc[n.category]) acc[n.category] = []
    acc[n.category].push(n)
    return acc
  }, {} as Record<string, NodeDefinition[]>)

  if (loading) {
    return (
      <div className="w-60 bg-[#181825] border-r border-[#313244] p-4 text-gray-400 text-sm">
        加载节点中...
      </div>
    )
  }

  return (
    <div className="w-60 bg-[#181825] border-r border-[#313244] overflow-y-auto">
      <div className="p-3 border-b border-[#313244]">
        <h3 className="text-sm font-medium text-white">节点面板</h3>
      </div>
      {Object.entries(grouped).map(([category, items]) => (
        <div key={category} className="p-2">
          <div className="text-xs text-gray-500 uppercase mb-2 px-2">
            {CATEGORY_LABELS[category] || category}
          </div>
          {items.map((node) => (
            <button
              key={node.type}
              onClick={() => handleAddNode(node)}
              className="w-full flex items-center gap-2 px-2 py-2 rounded hover:bg-[#313244] text-left transition-colors"
            >
              <span className={`w-2 h-2 rounded-full ${CATEGORY_COLORS[node.category] || 'bg-gray-500'}`} />
              <div className="flex-1 min-w-0">
                <div className="text-sm text-white truncate">{node.name}</div>
                <div className="text-xs text-gray-500 truncate">{node.description}</div>
              </div>
            </button>
          ))}
        </div>
      ))}
    </div>
  )
}
