/**
 * S3 一键出片任务（本地任务模型）+ R3 云端状态同步
 *  - drafting: Agent 生成脚本中 → scripted: 脚本已入资产库 → queued/rendering/done/failed（云端队列）
 *  - cap 100 条，持久化 localStorage
 *  - R3: syncFromCloud() 按 cloudJobId 回填服务端状态与错误
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { cloudListJobs, type CloudJob } from '@/utils/cloud'

export type JobStatus = 'drafting' | 'scripted' | 'queued' | 'rendering' | 'done' | 'failed'

export interface RenderJob {
  id: string
  templateSlug: string
  templateTitle: string
  genre: string
  premise: string
  status: JobStatus
  assetId?: string
  error?: string
  /** R3 云端任务主键（POST /api/comic/jobs 返回） */
  cloudJobId?: number
  createdAt: number
  updatedAt: number
}

interface JobState {
  jobs: RenderJob[]
  createJob: (j: { templateSlug: string; templateTitle: string; genre: string; premise: string }) => string
  updateJob: (id: string, patch: Partial<Pick<RenderJob, 'status' | 'assetId' | 'error' | 'cloudJobId'>>) => void
  removeJob: (id: string) => void
  clearDone: () => void
  // ---- R3 云端状态同步 ----
  syncFromCloud: () => Promise<{ ok: boolean; updated: number; message?: string }>
}

function jid(): string {
  return `job_${Date.now()}_${Math.floor(Math.random() * 1e4)}`
}

const LIMIT = 100

export const useJobStore = create<JobState>()(
  persist(
    (set, get) => ({
      jobs: [],
      createJob: (j) => {
        const id = jid()
        const now = Date.now()
        const job: RenderJob = { ...j, id, status: 'drafting', createdAt: now, updatedAt: now }
        set((s) => ({
          jobs: [job, ...s.jobs].slice(0, LIMIT),
        }))
        return id
      },
      updateJob: (id, patch) =>
        set((s) => ({
          jobs: s.jobs.map((job) =>
            job.id === id ? { ...job, ...patch, updatedAt: Date.now() } : job
          ),
        })),
      removeJob: (id) => set((s) => ({ jobs: s.jobs.filter((j) => j.id !== id) })),
      // 清理终态（scripted/failed/done），保留进行中（drafting/queued/rendering）
      clearDone: () =>
        set((s) => ({
          jobs: s.jobs.filter((j) => j.status === 'drafting' || j.status === 'queued' || j.status === 'rendering'),
        })),

      // ---- R3 云端状态同步：按 cloudJobId 回填服务端状态 ----
      syncFromCloud: async () => {
        const targets = get().jobs.filter((j) => j.cloudJobId)
        if (targets.length === 0) return { ok: true, updated: 0 }
        const r = await cloudListJobs()
        if (!r.ok) return { ok: false, updated: 0, message: r.message }
        const byId = new Map<number, CloudJob>()
        for (const c of r.data) byId.set(c.id, c)
        let updated = 0
        set((s) => ({
          jobs: s.jobs.map((j) => {
            if (!j.cloudJobId) return j
            const c = byId.get(j.cloudJobId)
            if (!c) return j
            const status = (['queued', 'rendering', 'done', 'failed'] as JobStatus[]).includes(c.status as JobStatus)
              ? (c.status as JobStatus)
              : j.status
            const error = c.error || undefined
            if (status === j.status && error === j.error) return j
            updated += 1
            return { ...j, status, error, updatedAt: Date.now() }
          }),
        }))
        return { ok: true, updated }
      },
    }),
    { name: 'yn.render.jobs' }
  )
)
