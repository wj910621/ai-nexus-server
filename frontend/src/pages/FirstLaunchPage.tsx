import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Steps, Button, Card, Checkbox, Radio, message, Spin } from 'antd'
import { Cloud, HardDrive, Shuffle, Crown } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { isElectron, RuntimeInfo } from '@/utils/runtime'
import { apiClient } from '@/api/client'
import { useAuthStore } from '@/stores/authStore'
import { ProviderSelector, ProviderPreference } from '@/components/settings/ProviderSelector'
import { HardwareProfile } from '@/api/models'
import termsMd from '@/legal/terms.md?raw'
import privacyMd from '@/legal/privacy.md?raw'

type Provider = 'cloud' | 'local' | 'hybrid'

export default function FirstLaunchPage() {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const [current, setCurrent] = useState(0)
  const [agreedTerms, setAgreedTerms] = useState(false)
  const [agreedPrivacy, setAgreedPrivacy] = useState(false)
  const [runtimeInfo, setRuntimeInfo] = useState<RuntimeInfo | null>(null)
  const [detecting, setDetecting] = useState(false)
  const [detectError, setDetectError] = useState<string | null>(null)
  const [provider, setProvider] = useState<Provider>('cloud')
  const [providerPref, setProviderPref] = useState<ProviderPreference | null>(null)
  const [dataDir, setDataDir] = useState('')
  const [telemetry, setTelemetry] = useState(true)
  const [autoUpdate, setAutoUpdate] = useState(true)
  const [cloudSync, setCloudSync] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // 根据已检测到的 runtimeInfo 推断硬件档位，供 ProviderSelector 使用
  const hardwareProfile: HardwareProfile = useMemo(() => {
    if (!runtimeInfo) return 'cpu'
    if (runtimeInfo.hasGpu) {
      if (runtimeInfo.vramMB >= 12288) return 'high' // 12GB+
      if (runtimeInfo.vramMB >= 8192) return 'mid'   // 8-12GB
      return 'low'
    }
    return 'cpu'
  }, [runtimeInfo])

  // Step 2 自动检测（仅 Desktop）
  useEffect(() => {
    if (current === 1 && isElectron) {
      setDetecting(true)
      window.electronAPI?.getRuntimeInfo?.()
        .then((info) => {
          setRuntimeInfo(info)
          setDetecting(false)
          // 根据 GPU 推荐默认 provider
          if (info.hasGpu && info.vramMB >= 8192) {
            setProvider('hybrid')
          }
        })
        .catch(() => {
          setDetectError('检测失败，将使用远程 API')
          setDetecting(false)
        })
    }
  }, [current])

  const isPro = user?.plan === 'pro'

  const canNext = () => {
    switch (current) {
      case 0:
        return agreedTerms && agreedPrivacy
      case 1:
        return true // 检测失败也允许下一步
      case 2:
        return true
      case 3:
        return true
      default:
        return false
    }
  }

  const handleNext = () => {
    if (current < 3) {
      setCurrent(current + 1)
    } else {
      handleComplete()
    }
  }

  const handlePrev = () => {
    if (current > 0) setCurrent(current - 1)
  }

  const handleComplete = async () => {
    setSubmitting(true)
    try {
      // 1. 保存 Provider 精细偏好到 localStorage（供 SettingsPage 复用）
      if (providerPref) {
        localStorage.setItem('provider_preferences', JSON.stringify(providerPref))
      }
      // 2. 保存偏好到后端
      await apiClient.put('/api/v1/users/me/preferences', {
        preferred_provider: provider,
        telemetry_enabled: telemetry,
        cloud_sync_enabled: cloudSync,
      })

      // 3. Desktop: 保存本地设置 + 标记首启完成
      if (isElectron) {
        await window.electronAPI!.saveSettings?.({ dataDir, telemetry, autoUpdate })
        await window.electronAPI!.completeFirstLaunch?.()
      }

      // 4. 标记首启完成
      await apiClient.put('/api/v1/users/me/first-launch', { completed: true })

      message.success('设置完成！')
      navigate('/dashboard')
    } catch {
      message.error('保存失败，请重试')
    } finally {
      setSubmitting(false)
    }
  }

  const steps = [
    {
      title: '欢迎与法律',
      content: (
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 700, marginBottom: 8 }}>
            欢迎使用 Y·NEX Story Studio
          </h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: 24 }}>
            一站式 AI 漫剧生成平台 · 让创作更简单
          </p>
          <Card title="用户协议" style={{ marginBottom: 16, maxHeight: 200, overflow: 'auto' }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{termsMd}</ReactMarkdown>
          </Card>
          <Card title="隐私政策" style={{ marginBottom: 16, maxHeight: 200, overflow: 'auto' }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{privacyMd}</ReactMarkdown>
          </Card>
          <Checkbox checked={agreedTerms} onChange={(e) => setAgreedTerms(e.target.checked)}>
            我已阅读并同意《用户协议》
          </Checkbox>
          <br />
          <Checkbox checked={agreedPrivacy} onChange={(e) => setAgreedPrivacy(e.target.checked)}>
            我已阅读并同意《隐私政策》
          </Checkbox>
        </div>
      ),
    },
    {
      title: '运行时检测',
      content: isElectron ? (
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>系统检测</h2>
          {detecting ? (
            <div style={{ textAlign: 'center', padding: 32 }}>
              <Spin size="large" />
              <p style={{ marginTop: 16, color: 'var(--text-secondary)' }}>正在检测本地 AI 运行时...</p>
            </div>
          ) : (
            <Card>
              {runtimeInfo ? (
                <div>
                  <p><strong>GPU:</strong> {runtimeInfo.gpuName || '未检测到'}</p>
                  <p><strong>VRAM:</strong> {runtimeInfo.vramMB} MB</p>
                  <p><strong>RAM:</strong> {runtimeInfo.ramMB} MB</p>
                  <p><strong>平台:</strong> {runtimeInfo.platform}</p>
                  <p><strong>推荐:</strong> {runtimeInfo.recommendedProvider}</p>
                </div>
              ) : (
                <p style={{ color: 'var(--accent-amber)' }}>{detectError}</p>
              )}
            </Card>
          )}
          <Button onClick={() => location.reload()} style={{ marginTop: 16 }}>重新检测</Button>
        </div>
      ) : (
        <div style={{ textAlign: 'center', padding: 32 }}>
          <p style={{ color: 'var(--text-secondary)' }}>Web 端跳过运行时检测</p>
        </div>
      ),
    },
    {
      title: 'AI Provider',
      content: (
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>选择 AI 方案</h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: 20 }}>
            选择适合你的 AI 推理方案，可随时在设置中更改
          </p>

          <Card
            style={{
              marginBottom: 12,
              border: provider === 'cloud' ? '2px solid var(--accent-emerald)' : '1px solid var(--border-default)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span><Cloud size={20} style={{ marginRight: 8 }} />云 API</span>
              {provider === 'cloud' && <span style={{ color: 'var(--accent-emerald)', fontSize: 12 }}>推荐</span>}
            </div>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              ✓ 高质量 SDXL/Qwen 模型 · 3-5s/图 · 无需本地 GPU<br />
              💳 需 Pro 订阅（¥39/月起）或使用免费试用额度
            </p>
            <Button type="primary" size="small" onClick={() => setProvider('cloud')}>
              选择
            </Button>
          </Card>

          <Card
            style={{
              marginBottom: 12,
              opacity: isPro ? 1 : 0.5,
              border: provider === 'local' ? '2px solid var(--brand-primary)' : '1px solid var(--border-default)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span><HardDrive size={20} style={{ marginRight: 8 }} />本地推理</span>
              <Crown size={14} style={{ color: 'var(--accent-violet)' }} />
            </div>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              ✓ 离线可用 · 零 API 成本<br />
              ⚠ 需要 8GB+ VRAM · GPU ~8s/图<br />
              {isPro ? '💳 Pro 福利' : '🔒 Free 用户不可用'}
            </p>
            {isPro ? (
              <Button size="small" onClick={() => setProvider('local')}>选择</Button>
            ) : (
              <Button size="small" onClick={() => navigate('/billing')}>升级 Pro 解锁</Button>
            )}
          </Card>

          <Card
            style={{
              marginBottom: 12,
              opacity: isPro ? 1 : 0.5,
              border: provider === 'hybrid' ? '2px solid var(--brand-primary)' : '1px solid var(--border-default)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span><Shuffle size={20} style={{ marginRight: 8 }} />混合模式</span>
              <Crown size={14} style={{ color: 'var(--accent-violet)' }} />
            </div>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              ✓ 优先本地推理 · 自动 fallback 云端<br />
              ✓ 最佳性价比 · 智能调度<br />
              {isPro ? '💳 Pro 专属' : '🔒 Free 用户不可用'}
            </p>
            {isPro && (
              <Button size="small" onClick={() => setProvider('hybrid')}>选择</Button>
            )}
          </Card>

          {/* Task 27: 细粒度 Provider 偏好（image/video/llm/tts） */}
          <Card
            title={<span>细粒度 Provider 偏好（按硬件档位 {hardwareProfile}）</span>}
            style={{ marginTop: 16, marginBottom: 12 }}
          >
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 12 }}>
              根据您的硬件配置（{hardwareProfile} 档位），系统已自动推荐合适的 Provider。
              您也可以手动调整偏好。
            </p>
            {runtimeInfo && (
              <div style={{ marginBottom: 12, padding: 8, background: 'var(--bg-secondary)', borderRadius: 4 }}>
                <strong>检测结果：</strong>
                {runtimeInfo.gpuName || (runtimeInfo.hasGpu ? 'GPU' : 'CPU')}（
                VRAM {(runtimeInfo.vramMB / 1024).toFixed(1)} GB / RAM{' '}
                {(runtimeInfo.ramMB / 1024).toFixed(1)} GB）
              </div>
            )}
            <ProviderSelector
              subscriptionTier={isPro ? 'pro' : 'free'}
              hardwareProfile={hardwareProfile}
              onChange={(pref) => setProviderPref(pref)}
            />
          </Card>
        </div>
      ),
    },
    {
      title: '数据与隐私',
      content: (
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>数据与隐私设置</h2>

          {isElectron && (
            <Card title="数据存储位置" style={{ marginBottom: 16 }}>
              <Radio.Group
                value={dataDir ? 'custom' : 'default'}
                onChange={(e) => {
                  if (e.target.value === 'custom') {
                    window.electronAPI?.chooseDirectory?.().then((dir) => {
                      if (dir) setDataDir(dir)
                    })
                  } else {
                    setDataDir('')
                  }
                }}
              >
                <Radio value="default">默认（~/Documents/ComicStudio）</Radio>
                <Radio value="custom">自定义 {dataDir && `(${dataDir})`}</Radio>
              </Radio.Group>
            </Card>
          )}

          <Card title="遥测数据" style={{ marginBottom: 16 }}>
            <Checkbox checked={telemetry} onChange={(e) => setTelemetry(e.target.checked)}>
              发送匿名使用统计（帮助我们改进）
            </Checkbox>
          </Card>

          {isElectron && (
            <Card title="自动更新" style={{ marginBottom: 16 }}>
              <Checkbox checked={autoUpdate} onChange={(e) => setAutoUpdate(e.target.checked)}>
                自动检查更新
              </Checkbox>
            </Card>
          )}

          <Card title="云端同步" style={{ marginBottom: 16 }}>
            <Checkbox
              checked={cloudSync}
              onChange={(e) => setCloudSync(e.target.checked)}
              disabled={!isPro}
            >
              启用项目云端同步 {isPro ? '' : '（Pro 功能）'}
            </Checkbox>
          </Card>
        </div>
      ),
    },
  ]

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: '32px 48px' }}>
      <Steps current={current} items={steps.map((s) => ({ title: s.title }))} style={{ marginBottom: 32 }} />

      <div style={{ minHeight: 300 }}>
        {steps[current].content}
      </div>

      <div style={{ marginTop: 24, paddingTop: 16, borderTop: '1px solid var(--border-default)', display: 'flex', justifyContent: 'space-between' }}>
        <Button onClick={handlePrev} disabled={current === 0}>← 上一步</Button>
        <Button
          type="primary"
          onClick={handleNext}
          disabled={!canNext()}
          loading={submitting}
        >
          {current === 3 ? '完成 →' : '下一步 →'}
        </Button>
      </div>
    </div>
  )
}
