import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import TrainingPage from '@/pages/TrainingPage'

vi.mock('@/api/training', () => ({
  createDataset: vi.fn().mockResolvedValue({
    data: {
      code: 0,
      data: {
        id: 'ds_1',
        character_id: 'ch_1',
        user_id: 'u_1',
        name: '训练数据集',
        status: 'drafting',
        image_count: 0,
        caption_mode: 'auto',
        trigger_word: '',
        created_at: '',
        items: [],
      },
    },
  }),
  getDataset: vi.fn(),
  getTrainStatus: vi.fn(),
  submitTrain: vi.fn(),
  deleteImage: vi.fn(),
}))

vi.mock('@/api/models', () => ({
  fetchRuntimeInfo: vi.fn().mockResolvedValue({
    data: { vram_gb: 24, gpu_name: 'RTX 4090' },
  }),
}))

vi.mock('@/components/training/DatasetUploader', () => ({
  default: () => <div data-testid="uploader">uploader</div>,
}))
vi.mock('@/components/training/CaptionEditor', () => ({
  default: () => <div data-testid="caption">caption</div>,
}))
vi.mock('@/components/training/TrainConfigForm', () => ({
  default: ({ setTriggerWord }: any) => (
    <div data-testid="config">
      <input
        data-testid="trigger-input"
        onChange={(e) => setTriggerWord(e.target.value)}
      />
    </div>
  ),
}))
vi.mock('@/components/training/TrainProgressPanel', () => ({
  default: () => <div data-testid="progress">progress</div>,
}))

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/training/ch_1']}>
      <Routes>
        <Route path="/training/:id" element={<TrainingPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('TrainingPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('挂载时应创建数据集', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('LoRA 训练')).toBeInTheDocument()
    })
    const { createDataset } = await import('@/api/training')
    expect(createDataset).toHaveBeenCalledWith({
      character_id: 'ch_1',
      name: expect.stringContaining('训练数据集'),
      caption_mode: 'auto',
      trigger_word: '',
    })
  })

  it('点击下一步应进入 Caption 步', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('下一步')).toBeInTheDocument())
    fireEvent.click(screen.getByText('下一步'))
    await waitFor(() => expect(screen.getByTestId('caption')).toBeInTheDocument())
  })
})
