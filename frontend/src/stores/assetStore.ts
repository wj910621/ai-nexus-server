/**
 * S2 统一任务/项目资产（本地离线模型）+ R3 云端同步
 *  - Agent 生成的漫剧脚本（comicScript）入库；后续渲染任务/分镜资产同表扩展
 *  - cap 200 条，持久化 localStorage
 *  - R3: 云端为增量层（本地优先）。pull 合并服务端资产（按 cloudId 去重、updated_at 胜出），
 *        push 上传尚未入云的本地资产；删除时同步清理云端副本。
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { cloudListAssets, cloudSaveAsset, cloudDeleteAsset } from '@/utils/cloud'

export type AssetKind = 'comic-script'

export interface ComicAsset {
  id: string
  kind: AssetKind
  title: string
  genre: string
  premise: string
  content: string // JSON 文本
  sessionId?: string
  createdAt: number
  /** R3 云端主键（未同步则 undefined） */
  cloudId?: number
  /** R3 上次同步时的服务端 updated_at */
  cloudUpdatedAt?: number
}

export type SyncStatus = 'idle' | 'syncing' | 'error' | 'offline'

export interface SyncOutcome {
  ok: boolean
  pulled: number
  pushed: number
  failed: number
  message?: string
}

interface AssetState {
  assets: ComicAsset[]
  addAsset: (a: Omit<ComicAsset, 'id' | 'createdAt'>) => string
  removeAsset: (id: string) => void
  clearAssets: () => void
  // ---- R3 云同步 ----
  syncStatus: SyncStatus
  syncMessage: string | null
  lastSyncAt: number | null
  pendingCount: () => number
  pullFromCloud: () => Promise<SyncOutcome>
  pushToCloud: (id?: string) => Promise<SyncOutcome>
  syncNow: () => Promise<SyncOutcome>
  removeAssetDeep: (id: string) => Promise<SyncOutcome>
}

function newId(): string {
  return `a_${Date.now()}_${Math.floor(Math.random() * 1e4)}`
}

export function parseTitleFromScript(content: string): string {
  try {
    const obj = JSON.parse(content) as { title?: string }
    return obj.title || '未命名脚本'
  } catch {
    return '未命名脚本'
  }
}

const EMPTY: SyncOutcome = { ok: true, pulled: 0, pushed: 0, failed: 0 }

export const useAssetStore = create<AssetState>()(
  persist(
    (set, get) => ({
      assets: [],
      addAsset: (a) => {
        const id = newId()
        set((s) => ({ assets: [{ ...a, id, createdAt: Date.now() }, ...s.assets].slice(0, 200) }))
        return id
      },
      removeAsset: (id) => set((s) => ({ assets: s.assets.filter((a) => a.id !== id) })),
      clearAssets: () => set({ assets: [] }),

      // ---- R3 云同步 ----
      syncStatus: 'idle',
      syncMessage: null,
      lastSyncAt: null,

      pendingCount: () => get().assets.filter((a) => !a.cloudId).length,

      pullFromCloud: async () => {
        set({ syncStatus: 'syncing', syncMessage: null })
        const r = await cloudListAssets('comic-script')
        if (!r.ok) {
          set({ syncStatus: r.code === 'unauthorized' ? 'offline' : 'error', syncMessage: r.message })
          return { ...EMPTY, ok: false, message: r.message }
        }
        let pulled = 0
        set((s) => {
          const merged = [...s.assets]
          const idxByCloud = new Map<number, number>()
          merged.forEach((a, i) => {
            if (a.cloudId) idxByCloud.set(a.cloudId, i)
          })
          for (const c of r.data) {
            const at = idxByCloud.get(c.id)
            if (at !== undefined) {
              const local = merged[at]
              if ((c.updated_at || 0) > (local.cloudUpdatedAt || 0)) {
                merged[at] = {
                  ...local,
                  title: c.title || local.title,
                  genre: c.genre || local.genre,
                  premise: c.premise ?? local.premise,
                  content: c.content || local.content,
                  cloudUpdatedAt: c.updated_at,
                }
                pulled += 1
              }
            } else {
              merged.unshift({
                id: `c_${c.id}`,
                kind: 'comic-script',
                title: c.title || '未命名脚本',
                genre: c.genre || '',
                premise: c.premise || '',
                content: c.content || '',
                createdAt: c.created_at || Date.now(),
                cloudId: c.id,
                cloudUpdatedAt: c.updated_at,
              })
              pulled += 1
            }
          }
          return { assets: merged.slice(0, 200), syncStatus: 'idle', lastSyncAt: Date.now(), syncMessage: null }
        })
        return { ...EMPTY, pulled }
      },

      pushToCloud: async (id) => {
        const targets = id
          ? get().assets.filter((a) => a.id === id)
          : get().assets.filter((a) => !a.cloudId)
        if (targets.length === 0) return { ...EMPTY }
        set({ syncStatus: 'syncing', syncMessage: null })
        let pushed = 0
        let failed = 0
        let lastMessage: string | undefined
        for (const a of targets) {
          const r = await cloudSaveAsset({
            kind: a.kind,
            title: a.title,
            genre: a.genre,
            premise: a.premise,
            content: a.content,
          })
          if (r.ok) {
            pushed += 1
            set((s) => ({
              assets: s.assets.map((x) =>
                x.id === a.id ? { ...x, cloudId: r.data.id, cloudUpdatedAt: Date.now() } : x,
              ),
            }))
          } else {
            failed += 1
            lastMessage = r.message
          }
        }
        set({
          syncStatus: failed > 0 ? 'error' : 'idle',
          syncMessage: lastMessage ?? null,
          lastSyncAt: Date.now(),
        })
        return { ok: failed === 0, pulled: 0, pushed, failed, message: lastMessage }
      },

      syncNow: async () => {
        const pull = await get().pullFromCloud()
        const push = await get().pushToCloud()
        return {
          ok: pull.ok && push.ok,
          pulled: pull.pulled,
          pushed: push.pushed,
          failed: push.failed + (pull.ok ? 0 : 1),
          message: push.message || pull.message,
        }
      },

      removeAssetDeep: async (id) => {
        const target = get().assets.find((a) => a.id === id)
        set((s) => ({ assets: s.assets.filter((a) => a.id !== id) }))
        if (!target?.cloudId) return { ...EMPTY }
        const r = await cloudDeleteAsset(target.cloudId)
        return { ok: r.ok, pulled: 0, pushed: 0, failed: r.ok ? 0 : 1, message: r.ok ? undefined : r.message }
      },
    }),
    { name: 'yn.agent.assets' },
  ),
)
