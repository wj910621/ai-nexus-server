import { apiClient } from './client'
import type { Character, CharacterCreate, ApiResponse, PaginatedResponse } from '@/types'

export const characterApi = {
  list(projectId?: string, page = 1, pageSize = 50) {
    return apiClient.get<PaginatedResponse<Character>>('/characters', {
      params: { project_id: projectId, page, page_size: pageSize },
    })
  },
  get(id: string) {
    return apiClient.get<ApiResponse<Character>>(`/characters/${id}`)
  },
  create(data: CharacterCreate) {
    return apiClient.post<ApiResponse<Character>>('/characters', data)
  },
  update(id: string, data: Partial<Character>) {
    return apiClient.put<ApiResponse<Character>>(`/characters/${id}`, data)
  },
  delete(id: string) {
    return apiClient.delete<ApiResponse<null>>(`/characters/${id}`)
  },
}
