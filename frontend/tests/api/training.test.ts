import { describe, it, expect, vi, beforeEach } from 'vitest'
import { submitTrain, getTrainStatus, createDataset, uploadImage, autoCaption } from '@/api/training'

// Mock apiClient
vi.mock('@/api/client', () => ({
  apiClient: {
    post: vi.fn(),
    get: vi.fn(),
    delete: vi.fn(),
  },
}))

import { apiClient } from '@/api/client'

describe('training API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('submitTrain 调用 POST /characters/{id}/train', async () => {
    ;(apiClient.post as any).mockResolvedValue({
      data: { code: 0, data: { task_id: 'task_1', character_id: 'ch_1', status: 'pending' } },
    })

    const result = await submitTrain('ch_1', {
      dataset_id: 'ds_1',
      location: 'local',
      trigger_word: 'zkq',
      preset: 'standard',
    })

    expect(apiClient.post).toHaveBeenCalledWith('/characters/ch_1/train', {
      dataset_id: 'ds_1',
      location: 'local',
      trigger_word: 'zkq',
      preset: 'standard',
    })
    expect(result.data.data.task_id).toBe('task_1')
  })

  it('getTrainStatus 调用 GET /characters/{id}/train/status', async () => {
    ;(apiClient.get as any).mockResolvedValue({
      data: { code: 0, data: { status: 'training', progress: 50, task_id: 'task_1' } },
    })

    const result = await getTrainStatus('ch_1')

    expect(apiClient.get).toHaveBeenCalledWith('/characters/ch_1/train/status')
    expect(result.data.data.status).toBe('training')
  })

  it('createDataset 调用 POST /datasets', async () => {
    ;(apiClient.post as any).mockResolvedValue({
      data: { code: 0, data: { id: 'ds_new', name: 'test' } },
    })

    const result = await createDataset({
      character_id: 'ch_1',
      name: 'test',
      caption_mode: 'auto',
      trigger_word: 'zkq',
    })

    expect(apiClient.post).toHaveBeenCalledWith('/datasets', {
      character_id: 'ch_1',
      name: 'test',
      caption_mode: 'auto',
      trigger_word: 'zkq',
    })
  })

  it('uploadImage 使用 FormData', async () => {
    ;(apiClient.post as any).mockResolvedValue({
      data: { code: 0, data: { id: 'di_1' } },
    })

    const file = new File(['x'], 'test.png', { type: 'image/png' })
    await uploadImage('ds_1', file)

    expect(apiClient.post).toHaveBeenCalledWith(
      '/datasets/ds_1/images',
      expect.any(FormData),
      expect.objectContaining({ headers: { 'Content-Type': 'multipart/form-data' } }),
    )
  })

  it('autoCaption 调用 POST /datasets/{id}/auto-caption', async () => {
    ;(apiClient.post as any).mockResolvedValue({
      data: { code: 0, data: { count: 5 } },
    })

    const result = await autoCaption('ds_1')
    expect(apiClient.post).toHaveBeenCalledWith('/datasets/ds_1/auto-caption')
    expect(result.data.data.count).toBe(5)
  })
})
