import { useCallback, useEffect, useState } from 'react'
import { Button, Card, Typography, message } from 'antd'
import { LoginOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { authApi } from '@/api/auth'
import { tokenStorage } from '@/utils/token'
import { useAuthStore } from '@/stores/authStore'

export default function LoginPage() {
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const setUser = useAuthStore((s) => s.setUser)

  const signInWithYnex = useCallback(async () => {
    setLoading(true)
    try {
      // The current Y·NEX portal stores its access token under auth_token.
      // Read it only to exchange for the short-lived, audience-restricted
      // Story token; never persist a second copy of the main-site token.
      const mainToken = localStorage.getItem('auth_token')
      if (!mainToken) {
        window.location.href = '/'
        return
      }
      const response = await fetch('/api/story/session', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${mainToken}`,
          'X-Requested-With': 'Y-NEX-Story-Studio',
        },
        credentials: 'same-origin',
      })
      const body = await response.json().catch(() => null)
      if (!response.ok || !body?.token) {
        throw new Error(body?.error || '无法建立漫剧工坊会话')
      }
      tokenStorage.setTokens(body.token, '')
      const userResponse = await authApi.getCurrentUser()
      const user = userResponse.data.data
      setUser(user)
      message.success('已进入漫剧工坊')
      navigate('/dashboard')
    } catch (e) {
      message.error(e instanceof Error ? e.message : '登录失败')
    } finally {
      setLoading(false)
    }
  }, [navigate, setUser])

  useEffect(() => {
    void signInWithYnex()
  }, [signInWithYnex])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#1e1e2e] to-[#11111b]">
      <Card className="w-96 !bg-[#1e1e2e] !border-[#313244]">
        <div className="text-center mb-6">
          <div className="w-16 h-16 mx-auto rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-bold text-2xl mb-3">
            Y
          </div>
          <Typography.Title level={3} className="!text-white !mb-0">
            Y·NEX Story Studio
          </Typography.Title>
          <Typography.Text className="!text-gray-400">使用 Y·NEX 主站账户进入</Typography.Text>
        </div>
        <Button type="primary" icon={<LoginOutlined />} loading={loading} block onClick={() => void signInWithYnex()}>
          使用 Y·NEX 账户进入
        </Button>
        <div className="text-center mt-4 text-gray-400 text-sm">账户注册、会员、积分与订单均由 Y·NEX 主站统一管理。</div>
      </Card>
    </div>
  )
}
