import { apiClient } from './client'
import type { LoginRequest, RegisterRequest, TokenResponse, User, ApiResponse } from '@/types'

export const authApi = {
  login(data: LoginRequest) {
    return apiClient.post<ApiResponse<TokenResponse>>('/auth/login', data)
  },
  register(data: RegisterRequest) {
    return apiClient.post<ApiResponse<User>>('/auth/register', data)
  },
  getCurrentUser() {
    return apiClient.get<ApiResponse<User>>('/users/me')
  },
  updateCurrentUser(data: Partial<User>) {
    return apiClient.put<ApiResponse<User>>('/users/me', data)
  },
}
