/**
 * 设置页
 *
 * Task 27: 新增 "AI Provider 偏好" Tab，集成 ProviderSelector 组件，
 * 允许用户在首启向导之后随时更改 image/video/llm/tts 偏好。
 *
 * P2 Task 16: 新增 "硬件基准测试" Tab，集成 BenchmarkCard 组件，
 * 展示 DeviceManager 检测结果与基准测试按钮。
 */
import { useState } from 'react'
import { Card, Tabs, Typography, message } from 'antd'
import { useAuthStore } from '@/stores/authStore'
import {
  ProviderSelector,
  ProviderPreference,
} from '@/components/settings/ProviderSelector'
import BenchmarkCard from '@/components/settings/BenchmarkCard'

type SubscriptionTier = 'free' | 'pro' | 'enterprise'

export default function SettingsPage() {
  const { user } = useAuthStore()
  const [providerPref, setProviderPref] = useState<ProviderPreference | null>(
    null,
  )

  // 用户订阅层级：user.plan 为 'free' | 'pro' | 'enterprise' 之一
  const subscriptionTier: SubscriptionTier =
    (user?.plan as SubscriptionTier) || 'free'

  // 从 localStorage 读取首启时保存的偏好作为初始值
  const initialPreference = (() => {
    try {
      return JSON.parse(
        localStorage.getItem('provider_preferences') || '{}',
      ) as Partial<ProviderPreference>
    } catch {
      return {}
    }
  })()

  function handleChange(pref: ProviderPreference) {
    setProviderPref(pref)
    try {
      localStorage.setItem('provider_preferences', JSON.stringify(pref))
      message.success('Provider 偏好已保存')
    } catch {
      message.error('保存失败，请重试')
    }
  }

  // 是否为管理员（仅 admin 可见基准测试 Tab）
  const isAdmin = (user?.role as string) === 'admin'

  return (
    <div className="p-6">
      <Typography.Title level={3} className="!text-white !mb-6">
        设置
      </Typography.Title>

      <Card className="!bg-[#1e1e2e] !border-[#313244]">
        <Tabs
          defaultActiveKey="provider"
          items={[
            {
              key: 'provider',
              label: 'AI Provider 偏好',
              children: (
                <div className="settings-provider-tab">
                  <p
                    style={{
                      color: 'var(--text-secondary)',
                      marginBottom: 16,
                    }}
                  >
                    设置默认使用的 AI Provider。系统会根据您的订阅层级自动过滤可选项；
                    本地 Provider 需要先下载模型才能启用。
                  </p>
                  <ProviderSelector
                    subscriptionTier={subscriptionTier}
                    initialPreference={initialPreference}
                    onChange={handleChange}
                  />
                  {providerPref && (
                    <div
                      style={{
                        marginTop: 16,
                        padding: 12,
                        background: 'var(--bg-secondary)',
                        borderRadius: 4,
                        color: 'var(--text-secondary)',
                      }}
                    >
                      已保存偏好：image={providerPref.image}, llm={providerPref.llm},
                      video={providerPref.video}, tts={providerPref.tts}
                    </div>
                  )}
                </div>
              ),
            },
            ...(isAdmin
              ? [
                  {
                    key: 'benchmark',
                    label: '硬件基准测试',
                    children: (
                      <div className="settings-benchmark-tab">
                        <p
                          style={{
                            color: 'var(--text-secondary)',
                            marginBottom: 16,
                          }}
                        >
                          运行硬件基准测试，评估当前设备的 LLM / 图像 / VRAM 性能。
                          测试结果用于自动选择最优 Provider 与硬件档位。
                        </p>
                        <BenchmarkCard />
                      </div>
                    ),
                  },
                ]
              : []),
          ]}
        />
      </Card>
    </div>
  )
}
