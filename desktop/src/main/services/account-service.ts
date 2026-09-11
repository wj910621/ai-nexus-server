import type { AccountUser, AccountResult } from '@shared/types'

/**
 * P1 统一账号层（主站 JWT 账号 ⇄ 桌面端）
 *
 * 设计目标（对齐合并评审 §P1）：
 *  - 主站账号为唯一真源：/api/auth/login、/api/user/data（积分/角色）
 *  - 存储采用 electron-store v11（默认导出 class），组件化以便单测（依赖注入 store/http）
 *  - 全部网络与存储路径有边界处理：未登录 / 过期 / 网络失败 / 存储不可用 -> 不抛未捕获异常
 *
 * 用法（main）:
 *   const service = createAccountService()   // electron 环境: new Store({ name: 'account' })
 */
export interface AccountStoreLike {
  get(key: string): unknown
  set(key: string, value: unknown): void
  delete(key: string): void
}


const DEFAULT_TIMEOUT_MS = 15_000

type HttpLike = (url: string, init?: { method?: string; headers?: Record<string, string>; body?: string; signal?: AbortSignal }) => Promise<{ ok: boolean; status: number; json(): Promise<unknown> }>

export class AccountService {
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

  async login(username: string, password: string): Promise<AccountResult<AccountUser>> {
    const u = (username || '').trim()
    const p = password || ''
    if (!u || !p) return { ok: false, code: 'invalid', message: '请输入账号与密码' }
    try {
      const ctrl = new AbortController()
      const timer = setTimeout(() => ctrl.abort(), DEFAULT_TIMEOUT_MS)
      const res = await this.http(`${this.apiBase}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: u, password: p }),
        signal: ctrl.signal,
      })
      clearTimeout(timer)
      const body = (await res.json().catch(() => null)) as { ok?: boolean; token?: string; error?: string; user?: AccountUser } | null
      if (!res.ok || !body?.ok || !body.token) {
        return { ok: false, code: res.status === 401 ? 'unauthorized' : 'invalid', message: body?.error || '登录失败' }
      }
      const user: AccountUser = {
        username: body.user?.username || u,
        email: body.user?.email,
        credits: typeof body.user?.credits === 'number' ? body.user.credits : 0,
        role: body.user?.role,
      }
      if (this.store) {
        try {
          this.store.set('token', body.token)
          this.store.set('username', user.username)
          this.store.set('email', user.email ?? '')
        } catch {
          return { ok: false, code: 'storage', message: '本地存储不可用' }
        }
      }
      return { ok: true, data: user }
    } catch (err) {
      const aborted = err instanceof Error && err.name === 'AbortError'
      return { ok: false, code: 'network', message: aborted ? '请求超时，请稍后重试' : '网络错误，请检查网络后重试' }
    }
  }

  async me(): Promise<AccountResult<AccountUser | null>> {
    const t = this.token
    if (!t) return { ok: true, data: null }
    try {
      const ctrl = new AbortController()
      const timer = setTimeout(() => ctrl.abort(), 12_000)
      const res = await this.http(`${this.apiBase}/api/user/data`, {
        headers: { Authorization: `Bearer ${t}` },
        signal: ctrl.signal,
      })
      clearTimeout(timer)
      if (res.status === 401) {
        this.clearToken()
        return { ok: true, data: null }
      }
      const body = (await res.json().catch(() => null)) as { ok?: boolean; data?: AccountUser; error?: string } | null
      if (!body?.ok || !body.data) return { ok: false, code: 'invalid', message: body?.error || '获取用户信息失败' }
      return { ok: true, data: body.data }
    } catch (err) {
      const aborted = err instanceof Error && err.name === 'AbortError'
      return { ok: false, code: 'network', message: aborted ? '请求超时' : '网络错误' }
    }
  }

  logout(): boolean {
    this.clearToken()
    return true
  }

  /**
   * SSO 换发 Y·NEX Story JWT（token 不出主进程，由 renderer 写入本地存储进入应用登录态）
   * 返回 { ok, token } / { ok:false, code, message }
   */
  async storyToken(): Promise<{ ok: true; token: string } | { ok: false; code: string; message: string }> {
    const t = this.token
    if (!t) return { ok: false, code: 'unauthorized', message: '请先登录主站账号' }
    try {
      const ctrl = new AbortController()
      const timer = setTimeout(() => ctrl.abort(), 12_000)
      const res = await this.http(`${this.apiBase}/api/story/session`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${t}` },
        signal: ctrl.signal,
      })
      clearTimeout(timer)
      if (res.status === 401 || res.status === 403) {
        this.clearToken()
        return { ok: false, code: 'unauthorized', message: '登录已过期，请重新登录' }
      }
      const body = (await res.json().catch(() => null)) as { ok?: boolean; token?: string; error?: string } | null
      if (!body?.ok || !body.token) {
        return { ok: false, code: 'invalid', message: body?.error || 'Story 会话换取失败' }
      }
      return { ok: true, token: body.token }
    } catch (err) {
      const aborted = err instanceof Error && err.name === 'AbortError'
      return { ok: false, code: 'network', message: aborted ? '请求超时' : '网络错误' }
    }
  }

  private clearToken(): void {
    try {
      this.store?.delete('token')
      this.store?.delete('username')
      this.store?.delete('email')
    } catch {
      /* 存储不可用时静默：token 仍在内存之外，下次 me() 仍会判定失败路径 */
    }
  }
}

/** electron 环境工厂：store 用 electron-store v11（默认导出 class），存储名 account */
export function createAccountService(): AccountService {
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
  return new AccountService(store, apiBase)
}
