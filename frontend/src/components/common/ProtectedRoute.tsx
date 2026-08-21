import { useEffect } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { tokenStorage } from '@/utils/token'

interface ProtectedRouteProps {
  children: React.ReactNode
}

export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, user } = useAuthStore()
  const location = useLocation()
  const navigate = useNavigate()
  const token = tokenStorage.getAccessToken()

  // 首启动检测：登录后若 first_launch_completed === false，跳转到首启页
  // 注意：/first-launch 路由在 ProtectedRoute 之外，跳转后不会再次触发本检测
  useEffect(() => {
    if (isAuthenticated && token && user?.preferences?.first_launch_completed === false) {
      navigate('/first-launch', { replace: true })
    }
  }, [isAuthenticated, token, user, navigate])

  if (!isAuthenticated || !token) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}
