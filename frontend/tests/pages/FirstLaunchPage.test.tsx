import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import FirstLaunchPage from '@/pages/FirstLaunchPage'

vi.mock('@/api/client', () => ({
  apiClient: { put: vi.fn().mockResolvedValue({}) },
}))

vi.mock('@/stores/authStore', () => ({
  useAuthStore: (selector: any) =>
    selector({ user: { id: 'u1', plan: 'free' } }),
}))

vi.mock('@/utils/runtime', () => ({
  isElectron: false,
}))

function renderPage() {
  return render(
    <MemoryRouter>
      <FirstLaunchPage />
    </MemoryRouter>
  )
}

async function goToStep(step: number) {
  if (step >= 1) {
    const checkboxes = screen.getAllByRole('checkbox')
    fireEvent.click(checkboxes[0])
    fireEvent.click(checkboxes[1])
  }
  for (let i = 0; i < step; i++) {
    await waitFor(() => {
      expect(screen.getByText('下一步 →')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByText('下一步 →'))
  }
}

describe('FirstLaunchPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('Step 1 未勾选协议时下一步应禁用', () => {
    renderPage()
    const nextBtn = screen.getByRole('button', { name: '下一步 →' })
    expect(nextBtn).toBeDisabled()
  })

  it('Step 1 勾选协议后可进入下一步', async () => {
    renderPage()

    const checkboxes = screen.getAllByRole('checkbox')
    fireEvent.click(checkboxes[0]) // 同意用户协议
    fireEvent.click(checkboxes[1]) // 同意隐私政策

    const nextBtn = screen.getByText('下一步 →')
    expect(nextBtn).not.toBeDisabled()

    fireEvent.click(nextBtn)

    // Step 2 Web 端跳过，应显示 Step 2 内容
    await waitFor(() => {
      expect(screen.getByText('Web 端跳过运行时检测')).toBeInTheDocument()
    })
  })

  it('Step 3 Free 用户本地推理应置灰', async () => {
    renderPage()

    await goToStep(2)

    await waitFor(() => {
      expect(screen.getByText('升级 Pro 解锁')).toBeInTheDocument()
    })
  })

  it('Web 端 Step 2 应自动跳过', async () => {
    renderPage()

    const checkboxes = screen.getAllByRole('checkbox')
    fireEvent.click(checkboxes[0])
    fireEvent.click(checkboxes[1])
    fireEvent.click(screen.getByText('下一步 →'))

    await waitFor(() => {
      expect(screen.getByText('Web 端跳过运行时检测')).toBeInTheDocument()
    })
  })

  it('完成应调用 API', async () => {
    const { apiClient } = await import('@/api/client')
    renderPage()

    // 快速走到最后一步
    const checkboxes = screen.getAllByRole('checkbox')
    fireEvent.click(checkboxes[0])
    fireEvent.click(checkboxes[1])

    await waitFor(() => screen.getByText('下一步 →'))
    fireEvent.click(screen.getByText('下一步 →'))

    await waitFor(() => screen.getByText('下一步 →'))
    fireEvent.click(screen.getByText('下一步 →'))

    await waitFor(() => screen.getByText('下一步 →'))
    fireEvent.click(screen.getByText('下一步 →'))

    // 走到最后一步后按钮变为 "完成 →"
    await waitFor(() => screen.getByText('完成 →'))
    fireEvent.click(screen.getByText('完成 →'))

    await waitFor(() => {
      expect(apiClient.put).toHaveBeenCalledWith(
        '/api/v1/users/me/preferences',
        expect.any(Object)
      )
      expect(apiClient.put).toHaveBeenCalledWith(
        '/api/v1/users/me/first-launch',
        { completed: true }
      )
    })
  })
})
