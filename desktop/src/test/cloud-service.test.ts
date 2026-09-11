/**
 * R3 cloud-service 单元测试
 * 覆盖：模板(公开/带 genre)、资产列表/保存(超限/空)/删除、任务入队(幂等)/列表、
 *       未登录 401、HTTP 4xx、网络异常、超时
 */
import { describe, it, expect, vi } from 'vitest'
import { CloudService } from '../main/services/cloud-service'
import type { AccountStoreLike } from '../main/services/account-service'

const BASE = 'https://ynexai.cn'

function memStore(withToken = true): AccountStoreLike {
  const m = new Map<string, unknown>()
  if (withToken) m.set('token', 'main.jwt.token')
  return {
    get: (k) => m.get(k),
    set: (k, v) => void m.set(k, v),
    delete: (k) => void m.delete(k),
  }
}

function okJson(status: number, body: unknown): { ok: boolean; status: number; json(): Promise<unknown> } {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}

describe('CloudService.templates', () => {
  it('未登录也可读（公开端点，不带 Authorization）', async () => {
    const http = vi.fn(async () => okJson(200, { ok: true, count: 1, items: [{ id: 1, slug: 's', title: 't', genre: '古风', description: 'd', price_credits: 10, shots: 8 }] }))
    const s = new CloudService(memStore(false), BASE, http as never)
    const r = await s.templates()
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data).toHaveLength(1)
    const init = (http.mock.calls[0] as unknown[])[1] as { headers: Record<string, string> }
    expect(init.headers.Authorization).toBeUndefined()
  })

  it('genre 透传且"全部"不下发', async () => {
    const http = vi.fn(async () => okJson(200, { ok: true, count: 0, items: [] }))
    const s = new CloudService(memStore(false), BASE, http as never)
    await s.templates('科幻')
    expect((http.mock.calls[0] as unknown[])[0]).toContain('genre=%E7%A7%91%E5%B9%BB')
    await s.templates('全部')
    expect((http.mock.calls[1] as unknown[])[0]).not.toContain('genre=')
  })

  it('网络异常 -> network', async () => {
    const http = vi.fn(async () => { throw new TypeError('down') })
    const s = new CloudService(memStore(false), BASE, http as never)
    const r = await s.templates()
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.code).toBe('network')
  })
})

describe('CloudService 鉴权', () => {
  it('未登录调用需鉴权端点 -> unauthorized，且不发请求', async () => {
    const http = vi.fn(async () => okJson(200, { ok: true, items: [] }))
    const s = new CloudService(memStore(false), BASE, http as never)
    const r = await s.listAssets()
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.code).toBe('unauthorized')
    expect(http).not.toHaveBeenCalled()
  })

  it('401 -> unauthorized', async () => {
    const http = vi.fn(async () => okJson(401, { ok: false, error: 'unauthorized' }))
    const s = new CloudService(memStore(), BASE, http as never)
    const r = await s.listJobs()
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.code).toBe('unauthorized')
  })

  it('超时 -> network(超时)', async () => {
    const http = vi.fn(async () => { throw new DOMException('Aborted', 'AbortError') })
    const s = new CloudService(memStore(), BASE, http as never)
    const r = await s.listAssets()
    expect(r.ok).toBe(false)
    if (!r.ok) {
      expect(r.code).toBe('network')
      expect(r.message).toContain('超时')
    }
  })
})

describe('CloudService.listAssets / saveAsset / deleteAsset', () => {
  it('列表返回 items', async () => {
    const http = vi.fn(async () => okJson(200, { ok: true, count: 1, items: [{ id: 7, kind: 'comic-script', title: 'a', genre: '古风', premise: 'p', content: '{}', created_at: 1, updated_at: 2 }] }))
    const s = new CloudService(memStore(), BASE, http as never)
    const r = await s.listAssets()
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data[0].id).toBe(7)
  })

  it('保存成功返回 id 且带默认 kind', async () => {
    const http = vi.fn(async () => okJson(200, { ok: true, id: 42 }))
    const s = new CloudService(memStore(), BASE, http as never)
    const r = await s.saveAsset({ title: 't', content: '{"a":1}' })
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data.id).toBe(42)
    const init = (http.mock.calls[0] as unknown[])[1] as { body: string }
    expect(JSON.parse(init.body).kind).toBe('comic-script')
  })

  it('空内容 -> invalid(不发请求)', async () => {
    const http = vi.fn(async () => okJson(200, { ok: true, id: 1 }))
    const s = new CloudService(memStore(), BASE, http as never)
    const r = await s.saveAsset({ content: '' })
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.code).toBe('invalid')
    expect(http).not.toHaveBeenCalled()
  })

  it('超过 512KB -> invalid', async () => {
    const http = vi.fn(async () => okJson(200, { ok: true, id: 1 }))
    const s = new CloudService(memStore(), BASE, http as never)
    const r = await s.saveAsset({ content: 'x'.repeat(512 * 1024 + 1) })
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.code).toBe('invalid')
    expect(http).not.toHaveBeenCalled()
  })

  it('删除：服务端 ok:false -> data false', async () => {
    const http = vi.fn(async () => okJson(200, { ok: false }))
    const s = new CloudService(memStore(), BASE, http as never)
    const r = await s.deleteAsset(9)
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data).toBe(false)
  })

  it('删除非法 id -> invalid', async () => {
    const http = vi.fn(async () => okJson(200, { ok: true }))
    const s = new CloudService(memStore(), BASE, http as never)
    const r = await s.deleteAsset(0)
    expect(r.ok).toBe(false)
    expect(http).not.toHaveBeenCalled()
  })
})

describe('CloudService.enqueueJob', () => {
  it('入队成功', async () => {
    const http = vi.fn(async () => okJson(200, { ok: true, jobId: 3 }))
    const s = new CloudService(memStore(), BASE, http as never)
    const r = await s.enqueueJob({ templateSlug: 'sci-mech-awaken', premise: 'p' })
    expect(r.ok).toBe(true)
    if (r.ok) {
      expect(r.data.jobId).toBe(3)
      expect(r.data.duplicate).toBe(false)
    }
  })

  it('幂等重复 -> duplicate true', async () => {
    const http = vi.fn(async () => okJson(200, { ok: true, jobId: 3, duplicate: true }))
    const s = new CloudService(memStore(), BASE, http as never)
    const r = await s.enqueueJob({ templateSlug: 's', idempotency: 'k1' })
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data.duplicate).toBe(true)
  })

  it('缺模板 -> invalid(不发请求)', async () => {
    const http = vi.fn(async () => okJson(200, { ok: true, jobId: 1 }))
    const s = new CloudService(memStore(), BASE, http as never)
    const r = await s.enqueueJob({ templateSlug: '  ' })
    expect(r.ok).toBe(false)
    expect(http).not.toHaveBeenCalled()
  })

  it('模板不存在 404 -> invalid 带服务端文案', async () => {
    const http = vi.fn(async () => okJson(404, { ok: false, error: '模板不存在' }))
    const s = new CloudService(memStore(), BASE, http as never)
    const r = await s.enqueueJob({ templateSlug: 'nope' })
    expect(r.ok).toBe(false)
    if (!r.ok) {
      expect(r.code).toBe('invalid')
      expect(r.message).toBe('模板不存在')
    }
  })
})

describe('CloudService.enqueueJob 分镜（R4b-2）', () => {
  it('分镜数组随请求下发并返回镜数', async () => {
    const http = vi.fn(async () => okJson(200, { ok: true, jobId: 9, shots: 3 }))
    const s = new CloudService(memStore(), BASE, http as never)
    const r = await s.enqueueJob({
      templateSlug: 's',
      shots: [{ prompt: '镜一' }, { prompt: '镜二' }, { prompt: '镜三' }],
    })
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data.shots).toBe(3)
    const init = (http.mock.calls[0] as unknown[])[1] as { body: string }
    expect(JSON.parse(init.body).shots).toHaveLength(3)
  })

  it('空 prompt 的分镜被过滤；全空则不下发 shots 字段', async () => {
    const http = vi.fn(async () => okJson(200, { ok: true, jobId: 1 }))
    const s = new CloudService(memStore(), BASE, http as never)
    await s.enqueueJob({ templateSlug: 's', shots: [{ prompt: '  ' }, { prompt: '' }] })
    const init = (http.mock.calls[0] as unknown[])[1] as { body: string }
    expect(JSON.parse(init.body).shots).toBeUndefined()
  })
})

describe('CloudService.tts（R4b-3）', () => {
  it('合成成功返回 base64 与元数据', async () => {
    const http = vi.fn(async () =>
      okJson(200, { ok: true, format: 'mp3', bytes: 43903, audio_base64: 'SUQzBA==', model: 'm', voice: 'v', chars: 12 }),
    )
    const s = new CloudService(memStore(), BASE, http as never)
    const r = await s.tts({ text: '这是漫剧工坊的语音通道测试。' })
    expect(r.ok).toBe(true)
    if (r.ok) {
      expect(r.data.format).toBe('mp3')
      expect(r.data.bytes).toBe(43903)
      expect(r.data.audioBase64).toBe('SUQzBA==')
      expect(r.data.chars).toBe(12)
    }
  })

  it('空文本 -> invalid 且不发请求', async () => {
    const http = vi.fn(async () => okJson(200, { ok: true }))
    const s = new CloudService(memStore(), BASE, http as never)
    const r = await s.tts({ text: '   ' })
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.code).toBe('invalid')
    expect(http).not.toHaveBeenCalled()
  })

  it('服务端未返回音频 -> invalid', async () => {
    const http = vi.fn(async () => okJson(200, { ok: true, format: 'mp3', bytes: 0 }))
    const s = new CloudService(memStore(), BASE, http as never)
    const r = await s.tts({ text: 'hello' })
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.message).toContain('未返回音频')
  })

  it('未登录 -> unauthorized', async () => {
    const http = vi.fn(async () => okJson(200, { ok: true }))
    const s = new CloudService(memStore(false), BASE, http as never)
    const r = await s.tts({ text: 'hello' })
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.code).toBe('unauthorized')
  })

  it('文本超限 400 -> invalid 带服务端文案', async () => {
    const http = vi.fn(async () => okJson(400, { ok: false, error: '文本超过 1500 字上限' }))
    const s = new CloudService(memStore(), BASE, http as never)
    const r = await s.tts({ text: 'x'.repeat(2000) })
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.message).toContain('1500')
  })
})
