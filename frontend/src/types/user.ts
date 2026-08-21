export interface User {
  id: string
  username: string
  email: string
  avatar_url: string | null
  bio: string | null
  status: string
  plan: string
  role: string
  credits: number
  preferences: Record<string, unknown>
  email_verified: boolean
  last_login_at: string | null
  created_at: string
}

export interface LoginRequest {
  account: string
  password: string
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: User
}

export interface ApiResponse<T> {
  code: number
  message: string
  data: T
  timestamp: number
}

export interface PaginatedResponse<T> {
  code: number
  message: string
  data: {
    items: T[]
    total: number
    page: number
    page_size: number
  }
  timestamp: number
}
