import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios'
import { tokenStorage } from '@/utils/token'
import type { ApiResponse } from '@/types'

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api'
const routerBase = (import.meta.env.VITE_ROUTER_BASE || '').replace(/\/$/, '')

export const apiClient: AxiosInstance = axios.create({
  baseURL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// 请求拦截：附加 Token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = tokenStorage.getAccessToken()
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截：统一处理错误
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiResponse<unknown>>) => {
    if (error.response) {
      const { status, data } = error.response
      // 401 未授权 - 清除 Token 并跳转登录
      if (status === 401) {
        tokenStorage.clear()
        const loginPath = `${routerBase}/login`
        if (window.location.pathname !== loginPath) {
          window.location.href = loginPath
        }
      }
      const detail = (data as ApiResponse<unknown> & { detail?: string })?.detail
      const message = detail || data?.message || '请求失败'
      return Promise.reject(new Error(message))
    }
    return Promise.reject(new Error('网络错误'))
  }
)
