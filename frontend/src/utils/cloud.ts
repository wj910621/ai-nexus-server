/**
 * R3 云服务桥（模板市场 / 云端资产同步 / 云渲染队列）
 *  - 桌面端：经主进程 IPC（渲染层为 file:// 源，无法直连主站 API；且主站 token 不出主进程）
 *  - 浏览器端：经 apiClient 同源 /api（与既有 SSO 会话一致）
 *  - 统一返回 CloudResult，调用方无需区分运行环境
 */
import { apiClient } from '@/api/client'
import { isDesktop } from './mainAccount'

export interface CloudTemplate {
  id: number
  slug: string
  title: string
  genre: string
  description: string
  /** 服务端为 snake_case（comic_cloud.js SELECT price_credits） */
  price_credits: number
  shots: number
  author?: string
}

export interface CloudAsset {
  id: number
  kind: string
  title: string
  genre: string
  premise: string
  content: string
  created_at: number
  updated_at: number
}

export interface CloudJob {
  id: number
  template_slug: string
  template_title: string
  genre: string
  premise: string
  status: 'queued' | 'rendering' | 'done' | 'failed'
  asset_id?: number | null
  error?: string | null
  created_at: number
  updated_at: number
}

export interface CloudAssetInput {
  kind?: string
  title?: string
  genre?: string
  premise?: string
  content: string
}

export type CloudResult<T> = { ok: true; data: T } | { ok: false; code: string; message: string }

function fail(err: unknown, fallback = '网络错误'): CloudResult<never> {
  const message = err instanceof Error ? err.message : fallback
  const code = /401|未授权|unauthorized|过期/i.test(message) ? 'unauthorized' : 'network'
  return { ok: false, code, message }
}

/** 桌面端 IPC 通道可用性 */
function desktopCloud() {
  return isDesktop() ? window.electronAPI?.cloud : undefined
}

export async function cloudTemplates(genre?: string): Promise<CloudResult<CloudTemplate[]>> {
  const api = desktopCloud()
  if (api) return (await api.templates(genre)) as CloudResult<CloudTemplate[]>
  try {
    const q = genre && genre !== '全部' ? `?genre=${encodeURIComponent(genre)}` : ''
    const res = await apiClient.get<{ ok: boolean; items: CloudTemplate[] }>(`/comic/templates${q}`)
    return { ok: true, data: res.data?.items ?? [] }
  } catch (err) {
    return fail(err)
  }
}

export async function cloudListAssets(kind?: string): Promise<CloudResult<CloudAsset[]>> {
  const api = desktopCloud()
  if (api) return (await api.listAssets(kind)) as CloudResult<CloudAsset[]>
  try {
    const q = kind ? `?kind=${encodeURIComponent(kind)}` : ''
    const res = await apiClient.get<{ ok: boolean; items: CloudAsset[] }>(`/user/assets${q}`)
    return { ok: true, data: res.data?.items ?? [] }
  } catch (err) {
    return fail(err)
  }
}

export async function cloudSaveAsset(input: CloudAssetInput): Promise<CloudResult<{ id: number }>> {
  const api = desktopCloud()
  if (api) return (await api.saveAsset(input)) as CloudResult<{ id: number }>
  try {
    const res = await apiClient.post<{ ok: boolean; id: number }>('/user/assets', {
      kind: input.kind || 'comic-script',
      title: input.title || '未命名',
      genre: input.genre || '',
      premise: input.premise || '',
      content: input.content,
    })
    return { ok: true, data: { id: Number(res.data?.id) || 0 } }
  } catch (err) {
    return fail(err)
  }
}

export async function cloudDeleteAsset(id: number): Promise<CloudResult<boolean>> {
  const api = desktopCloud()
  if (api) return (await api.deleteAsset(id)) as CloudResult<boolean>
  try {
    const res = await apiClient.delete<{ ok: boolean }>(`/user/assets/${id}`)
    return { ok: true, data: !!res.data?.ok }
  } catch (err) {
    return fail(err)
  }
}

export async function cloudEnqueueJob(job: {
  templateSlug: string
  premise?: string
  idempotency?: string
}): Promise<CloudResult<{ jobId: number; duplicate: boolean }>> {
  const api = desktopCloud()
  if (api) return (await api.enqueueJob(job)) as CloudResult<{ jobId: number; duplicate: boolean }>
  try {
    const res = await apiClient.post<{ ok: boolean; jobId: number; duplicate?: boolean }>('/comic/jobs', job)
    return { ok: true, data: { jobId: Number(res.data?.jobId) || 0, duplicate: !!res.data?.duplicate } }
  } catch (err) {
    return fail(err)
  }
}

export async function cloudListJobs(): Promise<CloudResult<CloudJob[]>> {
  const api = desktopCloud()
  if (api) return (await api.listJobs()) as CloudResult<CloudJob[]>
  try {
    const res = await apiClient.get<{ ok: boolean; items: CloudJob[] }>('/comic/jobs')
    return { ok: true, data: res.data?.items ?? [] }
  } catch (err) {
    return fail(err)
  }
}
