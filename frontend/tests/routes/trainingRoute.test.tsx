import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Outlet } from 'react-router-dom'

// Mock TrainingPage：渲染可识别标记，验证路由命中
vi.mock('@/pages/TrainingPage', () => ({
  default: () => <div data-testid="training-page">TrainingPage</div>,
}))

// Mock DashboardPage：catch-all 重定向目标，用于验证"未命中 train 路由"的失败情形
vi.mock('@/pages/DashboardPage', () => ({
  default: () => <div data-testid="dashboard-page">DashboardPage</div>,
}))

// Mock 其他 lazy 页面，避免引入真实依赖
vi.mock('@/pages/LoginPage', () => ({
  default: () => <div data-testid="login-page" />,
}))
vi.mock('@/pages/RegisterPage', () => ({
  default: () => <div data-testid="register-page" />,
}))
vi.mock('@/pages/ProjectListPage', () => ({
  default: () => <div data-testid="project-list-page" />,
}))
vi.mock('@/pages/ProjectEditorPage', () => ({
  default: () => <div data-testid="project-editor-page" />,
}))
vi.mock('@/pages/FirstLaunchPage', () => ({
  default: () => <div data-testid="first-launch-page" />,
}))
vi.mock('@/pages/SettingsPage', () => ({
  default: () => <div data-testid="settings-page" />,
}))

// Mock MainLayout：仅渲染 Outlet，避免 Sidebar/TopBar 依赖
vi.mock('@/components/layout/MainLayout', () => ({
  default: () => <Outlet />,
}))

// Mock ProtectedRoute：直接放行 children
vi.mock('@/components/common/ProtectedRoute', () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

describe('Training 路由注册', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('/characters/:id/train 应渲染 TrainingPage', async () => {
    const { default: AppRoutes } = await import('@/routes')

    render(
      <MemoryRouter initialEntries={['/characters/ch_1/train']}>
        <AppRoutes />
      </MemoryRouter>
    )

    // 命中 train 路由时应渲染 TrainingPage 标记
    await waitFor(() => {
      expect(screen.getByTestId('training-page')).toBeInTheDocument()
    })

    // 不应被 catch-all 重定向到 Dashboard
    expect(screen.queryByTestId('dashboard-page')).not.toBeInTheDocument()
  }, 30000)
})
