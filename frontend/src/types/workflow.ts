export interface WorkflowNode {
  id: string
  type: string
  position: { x: number; y: number }
  data: Record<string, unknown>
}

export interface WorkflowEdge {
  id: string
  source: string
  target: string
  sourceHandle?: string | null
  targetHandle?: string | null
}

export interface Workflow {
  id: string
  user_id: string
  project_id: string | null
  name: string
  description: string | null
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  category: string
  is_template: boolean
  is_public: boolean
  version: number
  created_at: string
  updated_at: string
}

export interface WorkflowCreate {
  name: string
  description?: string
  nodes?: WorkflowNode[]
  edges?: WorkflowEdge[]
  category?: string
  project_id?: string
}

export interface WorkflowUpdate {
  name?: string
  description?: string
  nodes?: WorkflowNode[]
  edges?: WorkflowEdge[]
  category?: string
  is_public?: boolean
}

export interface PortDefinition {
  name: string
  type: string  // image/text/audio/video/any/image_array
  required: boolean
  default?: unknown
  description?: string
}

export interface ParameterDefinition {
  name: string
  type: string  // int/float/text/bool/select
  default?: unknown
  min?: number
  max?: number
  options?: string[]
  description?: string
}

export interface NodeDefinition {
  type: string
  name: string
  category: string
  description: string
  icon: string
  inputs: PortDefinition[]
  outputs: PortDefinition[]
  parameters: ParameterDefinition[]
  is_async: boolean
  estimated_time: number
}

export interface WorkflowTemplate {
  template_id: string
  name: string
  description: string
  category: string
  is_premium: boolean
  workflow_data: { nodes: WorkflowNode[]; edges: WorkflowEdge[] }
  tags: string[]
  icon: string
}

export interface ExecutionProgress {
  execution_id: string
  status: string
  total: number
  completed: number
  progress: number
  started_at: number | null
  completed_at: number | null
  duration: number | null
}

export interface NodeExecutionRecord {
  node_id: string
  node_type: string
  status: string
  started_at: number | null
  completed_at: number | null
  duration: number | null
  result: Record<string, unknown> | null
  error: string | null
}

export interface ExecutionDetail {
  execution_id: string
  status: string
  started_at: number | null
  completed_at: number | null
  duration: number | null
  results: Record<string, Record<string, unknown>>
  errors: Record<string, string>
  node_executions: NodeExecutionRecord[]
  error: string | null
  progress: ExecutionProgress
}
