/**
 * P2 主站账号桥（桌面端优先 electronAPI.account；浏览器回退空实现）
 * 说明：桌面登录走主站 JWT（主站为账号真源）；浏览器环境仍走既有登录页流程。
 */
export interface MainAccount {
  username: string
  email?: string
  credits: number
  role?: string
}

export type MainAccountState =
  | { status: 'guest' }
  | { status: 'loading' }
  | { status: 'ready'; account: MainAccount }
  | { status: 'error'; message: string }

export function isDesktop(): boolean {
  return typeof window !== 'undefined' && !!window.electronAPI?.account
}

export async function desktopLogin(username: string, password: string): Promise<MainAccount> {
  if (!isDesktop()) throw new Error('桌面环境不可用')
  const api = window.electronAPI?.account
  if (!api) throw new Error('桌面环境不可用')
  const r = (await api.login(username, password)) as
    | { ok: true; data: MainAccount }
    | { ok: false; code: string; message: string }
  if (!r.ok) throw new Error((r as { message: string }).message || '登录失败')
  return (r as { data: MainAccount }).data
}

export async function desktopMe(): Promise<MainAccountState> {
  if (!isDesktop()) return { status: 'guest' }
  try {
    const api = window.electronAPI?.account
    if (!api) return { status: 'guest' }
    const r = (await api.me()) as
      | { ok: true; data: MainAccount | null }
      | { ok: false; code: string; message: string }
    if (!r.ok) return { status: 'error', message: (r as { message: string }).message || '获取账号失败' }
    const data = (r as { data: MainAccount | null }).data
    return data ? { status: 'ready', account: data } : { status: 'guest' }
  } catch {
    return { status: 'error', message: '无法连接主站' }
  }
}

export async function desktopLogout(): Promise<void> {
  if (isDesktop()) {
    try {
      await window.electronAPI?.account?.logout()
    } catch {
      /* 忽略登出异常 */
    }
  }
}
