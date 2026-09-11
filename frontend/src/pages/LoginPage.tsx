/**
 * 登录页（双模式）
 *  - 浏览器/主站 web 环境：读 localStorage 主站 token → /api/story/session SSO 进入（原逻辑）
 *  - 桌面端：主站 token 在主进程(electron-store) → account.storyToken() 静默 SSO；
 *    未登录主站则显示"主站账号登录"表单（desktopLogin → storyToken → 进入）
 */
import { useCallback, useEffect, useState } from 'react'
import { Button, Card, Divider, Input, Typography, message } from 'antd'
import { LoginOutlined, DesktopOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { authApi } from '@/api/auth'
import { tokenStorage } from '@/utils/token'
import { useAuthStore } from '@/stores/authStore'
import { isDesktop, desktopLogin } from '@/utils/mainAccount'

async function applyStoryToken(storyToken: string) {
  tokenStorage.setTokens(storyToken, '')
  const userResponse = await authApi.getCurrentUser()
  return userResponse.data.data
}

export default function LoginPage() {
  const [loading, setLoading] = useState(false)
  const [mainLoading, setMainLoading] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const navigate = useNavigate()
  const setUser = useAuthStore((s) => s.setUser)
  const desktop = isDesktop()

  const enter = useCallback(
    async (user: unknown) => {
      setUser(user as never)
      void message.success('已进入 Y·NEX Studio')
      navigate('/dashboard')
    },
    [navigate, setUser],
  )

  // 浏览器：读主站 localStorage token 走 SSO（原逻辑；桌面避免跳 '/' 死路）
  const signInWithYnex = useCallback(async () => {
    if (desktop) return
    setLoading(true)
    try {
      const mainToken = localStorage.getItem('auth_token')
      if (!mainToken) {
        void message.warning('请在 Y·NEX 主站登录后重试')
        return
      }
      const response = await fetch('/api/story/session', {
        method: 'POST',
        headers: { Authorization: `Bearer ${mainToken}`, 'X-Requested-With': 'Y-NEX-Story-Studio' },
        credentials: 'same-origin',
      })
      const body = await response.json().catch(() => null)
      if (!response.ok || !body?.token) throw new Error(body?.error || '无法建立漫剧工坊会话')
      await enter(await applyStoryToken(body.token))
    } catch (e) {
      void message.error(e instanceof Error ? e.message : '登录失败')
    } finally {
      setLoading(false)
    }
  }, [desktop, enter])

  // 桌面登录：有账号密码则 desktopLogin(主站) → storyToken → 进入
  const signInDesktop = useCallback(async () => {
    if (!desktop) return
    setMainLoading(true)
    try {
      const api = window.electronAPI?.account
      if (!api || !api.storyToken) throw new Error('桌面桥不可用')
      if (!username.trim() || !password) {
        void message.warning('请先输入主站账号与密码')
        return
      }
      await desktopLogin(username.trim(), password)
      const story = (await api.storyToken()) as { ok?: boolean; token?: string; message?: string }
      if (!story?.ok || !story.token) throw new Error(story?.message || 'Story 会话建立失败')
      await enter(await applyStoryToken(story.token))
    } catch (e) {
      void message.error(e instanceof Error ? e.message : '登录失败')
    } finally {
      setMainLoading(false)
    }
  }, [desktop, username, password, enter])

  useEffect(() => {
    void signInWithYnex()
  }, [signInWithYnex])

  // 桌面：自动静默 SSO（主进程已保存主站 token 时直达 dashboard）
  useEffect(() => {
    if (!desktop) return
    let cancelled = false
    void (async () => {
      try {
        const story = (await window.electronAPI?.account?.storyToken?.()) as { ok?: boolean; token?: string } | undefined
        if (!cancelled && story?.ok && story.token) {
          await enter(await applyStoryToken(story.token))
        }
      } catch {
        /* 主站未登录 → 显示表单 */
      }
    })()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [desktop])

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

        {desktop ? (
          <div className="space-y-2">
            <Input placeholder="主站用户名" value={username} onChange={(e) => setUsername(e.target.value)} />
            <Input.Password placeholder="主站密码" value={password} onChange={(e) => setPassword(e.target.value)} onPressEnter={() => void signInDesktop()} />
            <Button type="primary" icon={<DesktopOutlined />} loading={mainLoading} block onClick={() => void signInDesktop()}>
              登录主站账号进入
            </Button>
            <div className="text-center text-gray-500 text-xs pt-1">账号/积分/漫剧/Agent 由 ynexai.cn 主站统一管理</div>
          </div>
        ) : (
          <Button type="primary" icon={<LoginOutlined />} loading={loading} block onClick={() => void signInWithYnex()}>
            使用 Y·NEX 账户进入
          </Button>
        )}

        {desktop && (
          <Divider style={{ borderColor: '#313244' }}>
            <span className="text-gray-600 text-xs">桌面端直连</span>
          </Divider>
        )}
        <div className="text-center text-gray-400 text-sm">账户注册、会员、积分与订单均由 Y·NEX 主站统一管理。</div>
      </Card>
    </div>
  )
}
