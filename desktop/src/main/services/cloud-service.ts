/**
 * R3 云服务层（模板市场 / 云端资产同步 / 云渲染队列）
 *
 * 鉴权：主站 JWT（electron-store 'account' 的 token）。
 *   comic_cloud.js 使用 auth.verifyUserToken(主站 JWT) 校验，故此处复用 AccountService
 *   已持久化的主站 token，无需引入 Story JWT。
 *
 * 设计对齐 AccountService：依赖注入 store/http，便于离线单测；
 * 全部路径有边界处理（未登录/过期/网络失败/超限），不抛未捕获异常。
 */
import type { AccountStoreLike } from './account-service'

export interface CloudTemplate {
  id: number
  slug: string
  title: string
  genre: string
  description: string
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

export interface AssetInput {
  kind?: string
  title?: string
  genre?: string
  premise?: string
  content: string
}

export type CloudErrorCode = 'unauthorized' | 'network' | 'invalid'
export type CloudResult<T> = { ok: true; data: T } | { ok: false; code: CloudErrorCode; message: string }

const DEFAULT_TIMEOUT_MS = 15_000
/** 与 comic_cloud.js POST /api/user/assets 的 512KB 上限对齐 */
const MAX_CONTENT_BYTES = 512 * 1024

type HttpLike = (
  url: string,
  init?: { method?: string; headers?: Record<string, string>; body?: string; signal?: AbortSignal },
) => Promise<{ ok: boolean; status: number; json(): Promise<unknown> }>

interface RawInit {
  method?: string
  body?: unknown
  /** false = 公开端点（模板市场），不带 Authorization */
  auth?: boolean
}

export class CloudService {
  constructor(
    private readonly store: AccountStoreLike | null,
    private readonly apiBase: string,
    private readonly http: HttpLike = (...args) => fetch(...(args as [any, any])) as unknown as ReturnType<HttpLike>,
  ) {}

  get token(): string | null {
    try {
      const t = this.store?.get('token')
      return typeof t === 'string' && t.length > 0 ? t : null
    } catch {
      return null
    }
  }

  /** 统一的底层请求：返回原始响应体（2xx 且 JSON 可解析即视为传输成功） */
  private async raw(path: string, init: RawInit = {}): Promise<CloudResult<Record<string, unknown>>> {
    const needAuth = init.auth !== false
    const token = this.token
    if (needAuth && !token) return { ok: false, code: 'unauthorized', message: '请先登录主站账号' }
    try {
      const ctrl = new AbortController()
      const timer = setTimeout(() => ctrl.abort(), DEFAULT_TIMEOUT_MS)
      const headers: Record<string, string> = {}
      if (init.body !== undefined) headers['Content-Type'] = 'application/json'
      if (needAuth && token) headers.Authorization = `Bearer ${token}`
      const res = await this.http(`${this.apiBase}${path}`, {
        method: init.method || 'GET',
        headers,
        body: init.body === undefined ? undefined : JSON.stringify(init.body),
        signal: ctrl.signal,
      })
      clearTimeout(timer)
      if (res.status === 401 || res.status === 403) {
        return { ok: false, code: 'unauthorized', message: '登录已过期，请重新登录' }
      }
      const body = (await res.json().catch(() => null)) as Record<string, unknown> | null
      if (!res.ok || !body) {
        const err = typeof body?.error === 'string' ? body.error : `请求失败(${res.status})`
        return { ok: false, code: 'invalid', message: err }
      }
      return { ok: true, data: body }
    } catch (err) {
      const aborted = err instanceof Error && err.name === 'AbortError'
      return { ok: false, code: 'network', message: aborted ? '请求超时，请稍后重试' : '网络错误，请检查网络后重试' }
    }
  }

  /** GET /api/comic/templates（公开；genre 可选） */
  async templates(genre?: string): Promise<CloudResult<CloudTemplate[]>> {
    const q = genre && genre !== '全部' ? `?genre=${encodeURIComponent(genre)}` : ''
    const r = await this.raw(`/api/comic/templates${q}`, { auth: false })
    if (!r.ok) return r
    const items = Array.isArray(r.data.items) ? (r.data.items as CloudTemplate[]) : []
    return { ok: true, data: items }
  }

  /** GET /api/user/assets */
  async listAssets(kind?: string): Promise<CloudResult<CloudAsset[]>> {
    const q = kind ? `?kind=${encodeURIComponent(kind)}` : ''
    const r = await this.raw(`/api/user/assets${q}`)
    if (!r.ok) return r
    const items = Array.isArray(r.data.items) ? (r.data.items as CloudAsset[]) : []
    return { ok: true, data: items }
  }

  /** POST /api/user/assets（content 必填且 ≤512KB） */
  async saveAsset(input: AssetInput): Promise<CloudResult<{ id: number }>> {
    const content = typeof input.content === 'string' ? input.content : ''
    if (!content) return { ok: false, code: 'invalid', message: '脚本内容为空' }
    if (Buffer.byteLength(content, 'utf8') > MAX_CONTENT_BYTES) {
      return { ok: false, code: 'invalid', message: '内容超过 512KB 上限' }
    }
    const r = await this.raw('/api/user/assets', {
      method: 'POST',
      body: {
        kind: input.kind || 'comic-script',
        title: String(input.title || '未命名').slice(0, 120),
        genre: String(input.genre || ''),
        premise: String(input.premise || '').slice(0, 2000),
        content,
      },
    })
    if (!r.ok) return r
    return { ok: true, data: { id: Number(r.data.id) || 0 } }
  }

  /** DELETE /api/user/assets/:id */
  async deleteAsset(id: number): Promise<CloudResult<boolean>> {
    if (!Number.isFinite(id) || id <= 0) return { ok: false, code: 'invalid', message: '无效资产 ID' }
    const r = await this.raw(`/api/user/assets/${Math.floor(id)}`, { method: 'DELETE' })
    if (!r.ok) return r
    return { ok: true, data: !!r.data.ok }
  }

  /** POST /api/comic/jobs（幂等：同 idempotency 返回 duplicate；R4b-2 支持分镜数组） */
  async enqueueJob(input: {
    templateSlug: string
    premise?: string
    idempotency?: string
    shots?: { prompt: string }[]
  }): Promise<CloudResult<{ jobId: number; duplicate: boolean; shots: number }>> {
    const slug = String(input.templateSlug || '').trim()
    if (!slug) return { ok: false, code: 'invalid', message: '缺少模板标识' }
    const shots = Array.isArray(input.shots)
      ? input.shots
          .map((s) => ({ prompt: String(s?.prompt || '').trim().slice(0, 1200) }))
          .filter((s) => s.prompt.length > 0)
      : []
    const r = await this.raw('/api/comic/jobs', {
      method: 'POST',
      body: {
        templateSlug: slug,
        premise: String(input.premise || '').slice(0, 4000),
        ...(shots.length ? { shots } : {}),
        ...(input.idempotency ? { idempotency: String(input.idempotency).slice(0, 120) } : {}),
      },
    })
    if (!r.ok) return r
    return {
      ok: true,
      data: {
        jobId: Number(r.data.jobId) || 0,
        duplicate: !!r.data.duplicate,
        shots: Number(r.data.shots) || shots.length || 1,
      },
    }
  }

  /** GET /api/comic/jobs */
  async listJobs(): Promise<CloudResult<CloudJob[]>> {
    const r = await this.raw('/api/comic/jobs')
    if (!r.ok) return r
    const items = Array.isArray(r.data.items) ? (r.data.items as CloudJob[]) : []
    return { ok: true, data: items }
  }

  /** R4b-3 POST /api/comic/tts —— 语音合成（返回 mp3 base64） */
  async tts(input: { text: string; voice?: string; speed?: number }): Promise<CloudResult<TtsResult>> {
    const text = String(input.text || '').trim()
    if (!text) return { ok: false, code: 'invalid', message: '配音文本为空' }
    const r = await this.raw('/api/comic/tts', {
      method: 'POST',
      body: {
        text,
        ...(input.voice ? { voice: String(input.voice) } : {}),
        ...(Number.isFinite(input.speed) ? { speed: Number(input.speed) } : {}),
      },
    })
    if (!r.ok) return r
    const b64 = String(r.data.audio_base64 || '')
    if (!b64) return { ok: false, code: 'invalid', message: '服务端未返回音频数据' }
    return {
      ok: true,
      data: {
        format: String(r.data.format || 'mp3'),
        bytes: Number(r.data.bytes) || 0,
        audioBase64: b64,
        model: String(r.data.model || ''),
        voice: String(r.data.voice || ''),
        chars: Number(r.data.chars) || text.length,
      },
    }
  }
}

export interface TtsResult {
  format: string
  bytes: number
  audioBase64: string
  model: string
  voice: string
  chars: number
}

/** electron 环境工厂：复用 electron-store 'account'（与 AccountService 同源 token） */
export function createCloudService(): CloudService {
  let store: AccountStoreLike | null = null
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const mod = require('electron-store') as { default?: unknown }
    const Ctor = (mod?.default ?? mod) as new (o?: { name?: string }) => AccountStoreLike
    store = new Ctor({ name: 'account' })
  } catch {
    store = null
  }
  const apiBase = process.env.YNEX_API_BASE || 'https://ynexai.cn'
  return new CloudService(store, apiBase)
}
