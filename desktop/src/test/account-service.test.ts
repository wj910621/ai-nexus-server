/**
 * P1 account-service 单元测试
 * 覆盖：空参/成功/401/网络异常/超时/存储异常/未登录 me/登出清 token
 */
import { describe, it, expect, vi } from 'vitest'
import type { AccountResult } from '@shared/types'
import { AccountService, type AccountStoreLike } from '../main/services/account-service'

const BASE = 'https://ynexai.cn'

function memStore(): AccountStoreLike & { dump(): Record<string, unknown> } {
  const m = new Map<string, unknown>()
  return {
    get: (k) => m.get(k),
    set: (k, v) => void m.set(k, v),
    delete: (k) => void m.delete(k),
    dump: () => Object.fromEntries(m),
  }
}

function okJson(status: number, body: unknown): { ok: boolean; status: number; json(): Promise<unknown> } {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}

describe('AccountService.login', () => {
  it('空参数 -> invalid', async () => {
    const s = new AccountService(memStore(), BASE)
    const r = (await s.login('', '')) as Extract<AccountResult, { ok: false }>
    expect(r.ok).toBe(false)
    expect(r.code).toBe('invalid')
  })

  it('成功:存 token 并返回 user', async () => {
    const store = memStore()
    const http = vi.fn(async () => okJson(200, { ok: true, token: 'tok123', user: { username: 'wj0007', email: 'e@x.com', credits: 66, role: 'admin' } }))
    const s = new AccountService(store, BASE, http as never)
    const r = await s.login('wj0007', 'pw')
    expect(r.ok).toBe(true)
    if (r.ok) {
      expect(r.data.username).toBe('wj0007')
      expect(r.data.credits).toBe(66)
    }
    expect(store.dump().token).toBe('tok123')
  })

  it('401 -> unauthorized', async () => {
    const http = vi.fn(async () => okJson(401, { ok: false, error: '用户名或密码错误' }))
    const s = new AccountService(memStore(), BASE, http as never)
    const r = await s.login('wj0007', 'bad')
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.code).toBe('unauthorized')
  })

  it('网络异常 -> network', async () => {
    const http = vi.fn(async () => { throw new TypeError('fetch failed') })
    const s = new AccountService(memStore(), BASE, http as never)
    const r = await s.login('wj0007', 'pw')
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.code).toBe('network')
  })

  it('超时 -> network(aborted)', async () => {
    // 模拟真实 fetch abort：抛 AbortError（与 AbortController+setTimeout 超时行为一致）
    const http = vi.fn(async () => { throw new DOMException('Aborted', 'AbortError') })
    const s = new AccountService(memStore(), BASE, http as never)
    const r = await s.login('wj0007', 'pw')
    expect(r.ok).toBe(false)
    if (!r.ok) {
      expect(r.code).toBe('network')
      expect(r.message).toContain('超时')
    }
  })

  it('store 抛错 -> storage', async () => {
    const bad: AccountStoreLike = { get: () => null, set: () => { throw new Error('denied') }, delete: () => {} }
    const http = vi.fn(async () => okJson(200, { ok: true, token: 't', user: { username: 'u', credits: 0 } }))
    const s = new AccountService(bad, BASE, http as never)
    const r = await s.login('u', 'pw')
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.code).toBe('storage')
  })
})

describe('AccountService.me', () => {
  it('无 token -> data null', async () => {
    const s = new AccountService(memStore(), BASE)
    const r = await s.me()
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data).toBeNull()
  })

  it('401 -> 清 token 并返回 null', async () => {
    const store = memStore()
    store.set('token', 'expired')
    const http = vi.fn(async () => okJson(401, { error: 'unauthorized' }))
    const s = new AccountService(store, BASE, http as never)
    const r = await s.me()
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data).toBeNull()
    expect(store.dump().token).toBeUndefined()
  })

  it('成功返回用户', async () => {
    const store = memStore()
    store.set('token', 't1')
    const http = vi.fn(async () => okJson(200, { ok: true, data: { username: 'a', credits: 30, role: 'user' } }))
    const s = new AccountService(store, BASE, http as never)
    const r = await s.me()
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.data?.credits).toBe(30)
  })

  it('网络异常 -> network', async () => {
    const store = memStore()
    store.set('token', 't1')
    const http = vi.fn(async () => { throw new TypeError('down') })
    const s = new AccountService(store, BASE, http as never)
    const r = await s.me()
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.code).toBe('network')
  })
})

describe('AccountService.logout', () => {
  it('清除 token 字段', () => {
    const store = memStore()
    store.set('token', 't')
    store.set('username', 'u')
    const s = new AccountService(store, BASE)
    expect(s.logout()).toBe(true)
    expect(store.dump()).toEqual({})
  })
})

describe('AccountService.storyToken', () => {
  it('未登录 -> unauthorized', async () => {
    const s = new AccountService(memStore(), BASE)
    const r = await s.storyToken()
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.code).toBe('unauthorized')
  })

  it('成功换发 story JWT', async () => {
    const store = memStore()
    store.set('token', 'mainTok')
    const http = vi.fn(async () => okJson(200, { ok: true, token: 'story.jwt.xyz' }))
    const s = new AccountService(store, BASE, http as never)
    const r = await s.storyToken()
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.token).toBe('story.jwt.xyz')
  })

  it('401 -> 清 token 并 unauthorized', async () => {
    const store = memStore()
    store.set('token', 'expired')
    const http = vi.fn(async () => okJson(401, { error: 'x' }))
    const s = new AccountService(store, BASE, http as never)
    const r = await s.storyToken()
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.code).toBe('unauthorized')
    expect(store.dump().token).toBeUndefined()
  })

  it('网络异常 -> network', async () => {
    const store = memStore()
    store.set('token', 't')
    const http = vi.fn(async () => { throw new TypeError('down') })
    const s = new AccountService(store, BASE, http as never)
    const r = await s.storyToken()
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.code).toBe('network')
  })
})
