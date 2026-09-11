/**
 * S6a 右栏 AI 副驾驶 dock（账号 + 快捷入口真实动作）
 *  - 未登录 → 点击打开主站账号登录弹窗（desktopLogin）
 *  - 已登录 → 显示头像/用户名/积分；退出
 *  - 快捷入口：Agent/一键出片 真实跳转；本地 AI/绘画 标注开发中
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Input, Modal, Tag, Tooltip, message } from 'antd'
import {
  RightOutlined, LeftOutlined, ThunderboltOutlined, WalletOutlined,
  ExperimentOutlined, FileImageOutlined, RobotOutlined, LogoutOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons'
import { tokenStorage } from '@/utils/token'
import { useAgentStore } from '@/stores/agentStore'
import { useAssetStore } from '@/stores/assetStore'
import { useJobStore } from '@/stores/jobStore'
import { isDesktop, desktopLogin, desktopLogout, desktopMe, type MainAccountState } from '@/utils/mainAccount'

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2 py-0.5">
      <span className="text-gray-400">{label}</span>
      <span className="text-gray-100 text-right break-all max-w-[60%]">{value}</span>
    </div>
  )
}

export default function AiDock() {
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(false)
  const [acc, setAcc] = useState<MainAccountState>({ status: 'guest' })
  const [loginOpen, setLoginOpen] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const refresh = () => {
    desktopMe().then(setAcc).catch(() => setAcc({ status: 'guest' }))
  }

  useEffect(() => {
    refresh()
  }, [])

  const doLogin = async () => {
    if (!isDesktop()) {
      void message.warning('当前为浏览器预览，请在桌面端使用主站账号登录')
      return
    }
    if (!username.trim() || !password) {
      void message.info('请输入账号与密码')
      return
    }
    setSubmitting(true)
    try {
      await desktopLogin(username.trim(), password)
      setLoginOpen(false)
      setUsername('')
      setPassword('')
      refresh()
      void message.success('登录成功，云端余额已同步')
    } catch (err) {
      void message.error((err as Error).message || '登录失败')
    } finally {
      setSubmitting(false)
    }
  }

  const doLogout = async () => {
    await desktopLogout()
    setAcc({ status: 'guest' })
    void message.success('已退出主站账号')
  }

  const [aboutOpen, setAboutOpen] = useState(false)
  const [backendUrl, setBackendUrl] = useState('')

  const openAbout = async () => {
    setAboutOpen(true)
    try {
      const b = await window.electronAPI?.getBackendUrl?.()
      setBackendUrl(String(b ?? ''))
    } catch { /* ignore */ }
  }

  const go = (path: string) => navigate(path)

  if (collapsed) {
    return (
      <aside className="w-10 bg-[#1e1e2e] border-l border-[#313244] flex flex-col items-center py-3 gap-2">
        <Tooltip title="展开 AI 面板" placement="left">
          <Button type="text" size="small" icon={<LeftOutlined />} onClick={() => setCollapsed(false)} />
        </Tooltip>
      </aside>
    )
  }

  return (
    <aside className="w-64 bg-[#1e1e2e] border-l border-[#313244] flex flex-col overflow-hidden">
      <div className="h-10 flex items-center justify-between px-3 border-b border-[#313244]">
        <span className="text-xs font-semibold text-gray-300">AI 副驾驶</span>
        <Tooltip title="收起" placement="left">
          <Button type="text" size="small" icon={<RightOutlined />} onClick={() => setCollapsed(true)} />
        </Tooltip>
      </div>

      {/* 主站账号卡 */}
      <div className="px-3 py-3 border-b border-[#313244]">
        <div className="text-[11px] text-gray-500 mb-1">主站账号</div>
        {acc.status === 'loading' && <div className="text-xs text-gray-400">读取中…</div>}
        {acc.status === 'error' && <div className="text-xs text-amber-400">{acc.message}</div>}
        {acc.status === 'guest' && isDesktop() && (
          <Button type="primary" size="small" block onClick={() => setLoginOpen(true)}>
            登录主站账号
          </Button>
        )}
        {acc.status === 'guest' && !isDesktop() && (
          <div className="text-xs text-gray-400">未登录 · 浏览器预览请用右上角账号</div>
        )}
        {acc.status === 'ready' && (
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white text-sm font-bold shrink-0">
              {(acc.account.username[0] || 'U').toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-xs text-white truncate">{acc.account.username}</div>
              <div className="text-[11px] text-emerald-400">
                <WalletOutlined /> {acc.account.credits} 积分{acc.account.role === 'admin' ? ' · 管理员' : ''}
              </div>
            </div>
            <Tooltip title="退出主站账号">
              <Button size="small" type="text" icon={<LogoutOutlined />} onClick={() => void doLogout()} />
            </Tooltip>
          </div>
        )}
      </div>

      {/* 快捷入口（真实跳转/开发中标注） */}
      <div className="px-3 py-3 flex-1 overflow-auto">
        <div className="text-[11px] text-gray-500 mb-2">快捷入口</div>
        <div className="flex flex-col gap-1.5">
          <QuickItem icon={<RobotOutlined />} label="Agent 对话" hint="多模型创作智能" onClick={() => go('/agent')} />
          <QuickItem icon={<ThunderboltOutlined />} label="一键出片" hint="12 模板 → 分镜脚本" onClick={() => go('/templates')} />
          <QuickItem icon={<ExperimentOutlined />} label="本地 AI" hint="运行时后端（开发中）" disabled />
          <QuickItem icon={<FileImageOutlined />} label="AI 绘画" hint="云端渲染队列接入后开放" disabled />
        </div>
      </div>

      <div className="px-3 py-2 border-t border-[#313244] flex items-center justify-between">
        <div className="flex items-center gap-1 flex-wrap">
          <Tag color="processing" style={{ fontSize: 10 }}>账号:主站</Tag>
          <Tag color="success" style={{ fontSize: 10 }}>模型:云端</Tag>
        </div>
        <Tooltip title="关于与健康">
          <Button size="small" type="text" icon={<InfoCircleOutlined />} onClick={() => void openAbout()} />
        </Tooltip>
      </div>

      {/* 关于与健康 */}
      <Modal title="关于与健康" open={aboutOpen} footer={null} onCancel={() => setAboutOpen(false)} destroyOnClose>
        <div className="space-y-2 text-sm">
          <div><Info label="产品" value="Y·NEX Story Studio（一体化桌面）" /></div>
          <div><Info label="版本" value={isDesktop() ? '见安装包（0.3.x 系列）' : '浏览器预览（Web）'} /></div>
          <div><Info label="运行环境" value={isDesktop() ? '桌面端（Electron 主站直连）' : '浏览器（同源 Web）'} /></div>
          <div><Info label="主站账号" value={acc.status === 'ready' ? acc.account.username + ' · ' + acc.account.credits + ' 积分' : (acc.status === 'loading' ? '读取中…' : '未登录')} /></div>
          <div><Info label="Story 会话" value={tokenStorage.getAccessToken() ? '已建立' : '未建立'} /></div>
          <div><Info label="后端地址" value={backendUrl || '同源 /api'} /></div>
          <div><Info label="账号体系" value="主站 JWT → SSO Story JWT" /></div>
        </div>
        <div className="text-[11px] text-gray-500 mt-3">本地版本诊断：agentStore 会话数 {useAgentStore.getState().sessions.length} · 资产 {useAssetStore.getState().assets.length} · 任务 {useJobStore.getState().jobs.length}</div>
      </Modal>

      {/* 登录弹窗 */}
      <Modal
        title="登录主站账号"
        open={loginOpen}
        onOk={() => void doLogin()}
        onCancel={() => setLoginOpen(false)}
        okText="登录"
        cancelText="取消"
        confirmLoading={submitting}
        destroyOnClose
      >
        <div className="space-y-3 pt-2">
          <Input placeholder="用户名" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
          <Input.Password placeholder="密码" value={password} onChange={(e) => setPassword(e.target.value)} onPressEnter={() => void doLogin()} />
          <div className="text-[11px] text-gray-500">登录后余额/会员/漫剧/Agent 全互通（ynexai.cn 主站账号）</div>
        </div>
      </Modal>
    </aside>
  )
}

function QuickItem({
  icon, label, hint, onClick, disabled,
}: {
  icon: React.ReactNode
  label: string
  hint: string
  onClick?: () => void
  disabled?: boolean
}) {
  return (
    <button
      className={`w-full text-left rounded-lg px-2 py-1.5 transition-colors ${
        disabled ? 'cursor-not-allowed opacity-50' : 'hover:bg-[#2a2a3e]'
      }`}
      disabled={disabled}
      onClick={onClick}
    >
      <div className="flex items-center gap-2 text-sm text-gray-200">
        <span className="text-base">{icon}</span>
        <span className="text-xs">{label}</span>
      </div>
      <div className="text-[10px] text-gray-500 pl-6">{hint}</div>
    </button>
  )
}
