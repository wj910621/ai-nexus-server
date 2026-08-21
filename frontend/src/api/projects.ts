import { apiClient } from './client'
import type { Project, ProjectCreate, ProjectUpdate, ApiResponse, PaginatedResponse } from '@/types'

export const projectApi = {
  list(page = 1, pageSize = 20) {
    return apiClient.get<PaginatedResponse<Project>>('/projects', {
      params: { page, page_size: pageSize },
    })
  },
  get(id: string) {
    return apiClient.get<ApiResponse<Project>>(`/projects/${id}`)
  },
  create(data: ProjectCreate) {
    return apiClient.post<ApiResponse<Project>>('/projects', data)
  },
  update(id: string, data: ProjectUpdate) {
    return apiClient.put<ApiResponse<Project>>(`/projects/${id}`, data)
  },
  delete(id: string) {
    return apiClient.delete<ApiResponse<null>>(`/projects/${id}`)
  },
}
