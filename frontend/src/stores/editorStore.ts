import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'
import type {
  WorkflowNode,
  WorkflowEdge,
  ExecutionDetail,
  NodeDefinition,
  WorkflowTemplate,
} from '@/types'

interface EditorState {
  selectedNodeId: string | null
  isPlaying: boolean
  currentFrame: number
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  isExecuting: boolean
  executionDetail: ExecutionDetail | null
  availableNodes: NodeDefinition[]
  templates: WorkflowTemplate[]
  selectNode: (id: string | null) => void
  setNodes: (nodes: WorkflowNode[]) => void
  setEdges: (edges: WorkflowEdge[]) => void
  addNode: (node: WorkflowNode) => void
  removeNode: (id: string) => void
  setIsExecuting: (v: boolean) => void
  setExecutionDetail: (d: ExecutionDetail | null) => void
  setAvailableNodes: (n: NodeDefinition[]) => void
  setTemplates: (t: WorkflowTemplate[]) => void
  play: () => void
  pause: () => void
  setFrame: (frame: number) => void
}

export const useEditorStore = create<EditorState>()(
  immer((set) => ({
    selectedNodeId: null,
    isPlaying: false,
    currentFrame: 0,
    nodes: [],
    edges: [],
    isExecuting: false,
    executionDetail: null,
    availableNodes: [],
    templates: [],
    selectNode: (id) =>
      set((state) => {
        state.selectedNodeId = id
      }),
    setNodes: (nodes) =>
      set((state) => {
        state.nodes = nodes
      }),
    setEdges: (edges) =>
      set((state) => {
        state.edges = edges
      }),
    addNode: (node) =>
      set((state) => {
        state.nodes.push(node)
      }),
    removeNode: (id) =>
      set((state) => {
        state.nodes = state.nodes.filter((n) => n.id !== id)
        state.edges = state.edges.filter((e) => e.source !== id && e.target !== id)
      }),
    setIsExecuting: (v) =>
      set((state) => {
        state.isExecuting = v
      }),
    setExecutionDetail: (d) =>
      set((state) => {
        state.executionDetail = d
      }),
    setAvailableNodes: (n) =>
      set((state) => {
        state.availableNodes = n
      }),
    setTemplates: (t) =>
      set((state) => {
        state.templates = t
      }),
    play: () =>
      set((state) => {
        state.isPlaying = true
      }),
    pause: () =>
      set((state) => {
        state.isPlaying = false
      }),
    setFrame: (frame) =>
      set((state) => {
        state.currentFrame = frame
      }),
  }))
)
