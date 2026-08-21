import { useCallback, useMemo } from 'react'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  addEdge,
  applyNodeChanges,
  applyEdgeChanges,
  type Node,
  type Edge,
  type OnNodesChange,
  type OnEdgesChange,
  type OnConnect,
  type NodeTypes,
} from 'reactflow'
import 'reactflow/dist/style.css'
import ImageGenNode from './nodes/ImageGenNode'
import CharacterNode from './nodes/CharacterNode'
import LLMChatNode from './nodes/LLMChatNode'
import TTSNode from './nodes/TTSNode'
import VideoComposeNode from './nodes/VideoComposeNode'
import TextInputNode from './nodes/TextInputNode'
import TextConcatNode from './nodes/TextConcatNode'
import ImagePreviewNode from './nodes/ImagePreviewNode'
import NodePalette from './NodePalette'
import ExecutionPanel from './ExecutionPanel'
import { useEditorStore } from '@/stores/editorStore'

const nodeTypes: NodeTypes = {
  imageGen: ImageGenNode,
  character: CharacterNode,
  text_to_image: ImageGenNode,
  character_gen: CharacterNode,
  llm_chat: LLMChatNode,
  tts: TTSNode,
  video_compose: VideoComposeNode,
  text_input: TextInputNode,
  text_concat: TextConcatNode,
  image_preview: ImagePreviewNode,
}

const defaultEdgeOptions = {
  style: { stroke: '#6366f1', strokeWidth: 2 },
  animated: true,
}

export default function WorkflowEditor() {
  const { nodes, edges, setNodes, setEdges } = useEditorStore()

  const onNodesChange: OnNodesChange = useCallback(
    (changes) => {
      const updated = applyNodeChanges(changes, nodes as Node[])
      setNodes(updated as unknown as typeof nodes)
    },
    [nodes, setNodes]
  )

  const onEdgesChange: OnEdgesChange = useCallback(
    (changes) => {
      const updated = applyEdgeChanges(changes, edges as Edge[])
      setEdges(updated as unknown as typeof edges)
    },
    [edges, setEdges]
  )

  const onConnect: OnConnect = useCallback(
    (connection) => {
      const updated = addEdge({ ...connection, ...defaultEdgeOptions }, edges as Edge[])
      setEdges(updated as unknown as typeof edges)
    },
    [edges, setEdges]
  )

  const minimapStyle = useMemo(() => ({ backgroundColor: '#1e1e2e' }), [])

  return (
    <div className="w-full h-full flex flex-col">
      <div className="flex-1 flex overflow-hidden">
        <NodePalette />
        <div className="flex-1 relative">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            nodeTypes={nodeTypes}
            defaultEdgeOptions={defaultEdgeOptions}
            fitView
            className="bg-[#181825]"
          >
            <Background color="#313244" gap={16} />
            <Controls className="!bg-[#2a2a3e] !border-[#313244]" />
            <MiniMap style={minimapStyle} nodeColor="#6366f1" maskColor="rgba(0,0,0,0.5)" />
          </ReactFlow>
        </div>
      </div>
      <ExecutionPanel />
    </div>
  )
}
