import { apiClient } from './client'
import type {
  Workflow, WorkflowCreate, WorkflowUpdate, ApiResponse, PaginatedResponse,
  WorkflowNode, WorkflowEdge,
  NodeDefinition, WorkflowTemplate, ExecutionDetail, ExecutionProgress,
} from '@/types'

export const workflowApi = {
  list(page = 1, pageSize = 50) {
    return apiClient.get<PaginatedResponse<Workflow>>('/workflows', {
      params: { page, page_size: pageSize },
    })
  },
  get(id: string) {
    return apiClient.get<ApiResponse<Workflow>>(`/workflows/${id}`)
  },
  create(data: WorkflowCreate) {
    return apiClient.post<ApiResponse<Workflow>>('/workflows', data)
  },
  update(id: string, data: WorkflowUpdate) {
    return apiClient.put<ApiResponse<Workflow>>(`/workflows/${id}`, data)
  },
  delete(id: string) {
    return apiClient.delete<ApiResponse<null>>(`/workflows/${id}`)
  },
}

export const workflowEngineApi = {
  execute(data: {
    workflow_id?: string
    nodes?: Array<{ id: string; type: string; params: Record<string, unknown> }>
    edges?: Array<{ from: string; to: string; from_port: string; to_port: string }>
    inputs?: Record<string, unknown>
  }) {
    return apiClient.post<ApiResponse<ExecutionDetail>>('/workflows/execute', data)
  },

  getExecutionStatus(executionId: string) {
    return apiClient.get<ApiResponse<ExecutionProgress>>(`/workflows/executions/${executionId}/status`)
  },

  cancelExecution(executionId: string) {
    return apiClient.post<ApiResponse<null>>(`/workflows/executions/${executionId}/cancel`)
  },

  listNodes() {
    return apiClient.get<ApiResponse<NodeDefinition[]>>('/workflows/nodes')
  },

  listTemplates(params?: { category?: string; include_premium?: boolean }) {
    return apiClient.get<ApiResponse<WorkflowTemplate[]>>('/workflows/templates', { params })
  },

  applyTemplate(data: { template_id: string; customizations?: Record<string, unknown> }) {
    return apiClient.post<ApiResponse<{ nodes: WorkflowNode[]; edges: WorkflowEdge[] }>>(
      '/workflows/apply-template', data
    )
  },
}
