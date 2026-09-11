/**
 * S3 漫剧模板画廊 + 一键出片任务卡
 *  - R3: 模板来源为云端 /api/comic/templates（公开），失败自动回退 12 条内置种子
 *  - 一键出片：Agent 真实生成分镜脚本(createComicScript) → 脚本入资产库 → 云端队列入队(POST /api/comic/jobs)
 *  - 任务卡：状态/复制脚本/删除
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Button, Empty, Input, Select, Space, Spin, Tag, Tooltip, Typography, message } from 'antd'
import {
  PlayCircleOutlined, ClockCircleOutlined, CheckCircleOutlined, CloseCircleOutlined,
  CopyOutlined, DeleteOutlined, SyncOutlined, CloudOutlined, CloudDownloadOutlined, PictureOutlined,
} from '@ant-design/icons'
import { isDesktop } from '@/utils/mainAccount'
import { useJobStore, type RenderJob } from '@/stores/jobStore'
import { useAssetStore, parseTitleFromScript } from '@/stores/assetStore'
import { cloudTemplates, cloudEnqueueJob, cloudListAssets, type CloudTemplate, type CloudAsset } from '@/utils/cloud'

interface SeedTemplate {
  slug: string
  title: string
  genre: string
  description: string
  priceCredits: number
  shots: number
}

const SEED_TEMPLATES: SeedTemplate[] = [
  { slug: 'ancient-xianxia-basic', title: '仙侠·逆袭归来', genre: '古风', description: '修仙少年逆袭归来，热血打脸三幕式。', priceCredits: 10, shots: 8 },
  { slug: 'ancient-wuxia-jianghu', title: '武侠·刀客行', genre: '古风', description: '江湖恩怨、快意恩仇，利落打斗分镜。', priceCredits: 10, shots: 8 },
  { slug: 'ancient-palace-dou', title: '古言·深宫谋', genre: '古风', description: '深宫权谋与情感反转，服饰精致。', priceCredits: 10, shots: 10 },
  { slug: 'sci-mech-awaken', title: '科幻·觉醒', genre: '科幻', description: '废土机械觉醒，末日机甲对决。', priceCredits: 10, shots: 8 },
  { slug: 'sci-space-explorer', title: '科幻·深空探索', genre: '科幻', description: '太空舰队深空探险，未知文明接触。', priceCredits: 10, shots: 8 },
  { slug: 'sci-cyber-city', title: '赛博·义体人', genre: '科幻', description: '霓虹都市义体人悬案，赛博朋克氛围。', priceCredits: 10, shots: 8 },
  { slug: 'urban-romance-office', title: '都市·办公室恋曲', genre: '都市', description: '职场轻喜爱情，日常甜宠向。', priceCredits: 10, shots: 8 },
  { slug: 'urban-food-truck', title: '都市·深夜食堂', genre: '都市', description: '治愈系美食故事，暖色系画面。', priceCredits: 10, shots: 8 },
  { slug: 'urban-detective', title: '都市·侦探社', genre: '都市', description: '高智商破案单元剧，抽丝剥茧。', priceCredits: 10, shots: 8 },
  { slug: 'susp-mansion', title: '悬疑·古宅迷案', genre: '悬疑', description: '封闭古宅连环迷案，反转结局。', priceCredits: 10, shots: 10 },
  { slug: 'susp-psycho', title: '悬疑·心理游戏', genre: '悬疑', description: '心理博弈双人对决，意象化画面。', priceCredits: 10, shots: 8 },
  { slug: 'susp-desert', title: '悬疑·沙漠孤站', genre: '悬疑', description: '荒漠孤站信号消失，细思极恐。', priceCredits: 10, shots: 8 },
]

const STATUS_META: Record<RenderJob['status'], { label: string; color: string; icon: React.ReactNode }> = {
  drafting: { label: '脚本生成中', color: 'processing', icon: <ClockCircleOutlined /> },
  scripted: { label: '脚本已就绪', color: 'success', icon: <CheckCircleOutlined /> },
  queued: { label: '云端排队中', color: 'warning', icon: <ClockCircleOutlined /> },
  rendering: { label: '云端渲染中', color: 'processing', icon: <SyncOutlined spin /> },
  done: { label: '已完成', color: 'success', icon: <CheckCircleOutlined /> },
  failed: { label: '失败', color: 'error', icon: <CloseCircleOutlined /> },
}

export default function TemplatesPage() {
  const [genre, setGenre] = useState('全部')
  const [active, setActive] = useState<SeedTemplate | null>(null)
  const [premise, setPremise] = useState('')
  const [starting, setStarting] = useState(false)
  const [templates, setTemplates] = useState<SeedTemplate[]>(SEED_TEMPLATES)
  const [source, setSource] = useState<'cloud' | 'local'>('local')
  const [loading, setLoading] = useState(false)
  const [renders, setRenders] = useState<CloudAsset[]>([])
  const [renderLoading, setRenderLoading] = useState(false)
  const { jobs, createJob, updateJob, removeJob, syncFromCloud } = useJobStore()
  const addAsset = useAssetStore((s) => s.addAsset)

  const loadTemplates = useCallback(async () => {
    setLoading(true)
    try {
      const r = await cloudTemplates()
      if (r.ok && r.data.length > 0) {
        setTemplates(
          r.data.map((t: CloudTemplate) => ({
            slug: t.slug,
            title: t.title,
            genre: t.genre,
            description: t.description,
            priceCredits: t.price_credits,
            shots: t.shots,
          })),
        )
        setSource('cloud')
      } else {
        setTemplates(SEED_TEMPLATES)
        setSource('local')
      }
    } catch {
      setTemplates(SEED_TEMPLATES)
      setSource('local')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadTemplates()
  }, [loadTemplates])

  /** R3: 拉取云端成片资产（kind=comic-render，由服务端 worker 渲染完成后写入） */
  const loadRenders = useCallback(async () => {
    setRenderLoading(true)
    try {
      const r = await cloudListAssets('comic-render')
      setRenders(r.ok ? r.data : [])
    } finally {
      setRenderLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadRenders()
  }, [loadRenders])

  /** R3: 同步云端任务状态（queued→rendering→done/failed） */
  const syncCloud = async () => {
    const r = await syncFromCloud()
    if (!r.ok) {
      void message.warning(`云端状态同步失败：${r.message ?? '请检查主站登录状态'}`)
      return
    }
    void message.success(r.updated > 0 ? `已更新 ${r.updated} 个任务状态` : '任务状态已是最新')
    await loadRenders()
  }

  /** 解析成片资产中的图片 URL */
  const renderImages = (a: CloudAsset): string[] => {
    try {
      const obj = JSON.parse(a.content) as { images?: string[] }
      return Array.isArray(obj.images) ? obj.images : []
    } catch {
      return []
    }
  }

  const genres = useMemo(() => ['全部', ...Array.from(new Set(templates.map((t) => t.genre)))], [templates])
  const list = genre === '全部' ? templates : templates.filter((t) => t.genre === genre)

  const quickStart = async (tpl: SeedTemplate) => {
    if (!isDesktop()) {
      void message.warning('请在桌面端使用主站账号登录后体验')
      return
    }
    const api = window.electronAPI?.agent
    if (!api) {
      void message.error('Agent 桥不可用')
      return
    }
    const text = premise.trim()
    setActive(tpl)
    setStarting(true)
    const jobId = createJob({ templateSlug: tpl.slug, templateTitle: tpl.title, genre: tpl.genre, premise: text || '（未填写，按模板默认题材）' })
    try {
      const r = (await api.createComicScript(text || `创作一个${tpl.genre}题材故事`, tpl.genre)) as
        | { ok: true; content: string }
        | { ok: false; code: string; message: string }
      if (!r.ok) throw new Error((r as { message: string }).message || '生成失败')
      const content = (r as { content: string }).content
      const title = parseTitleFromScript(content)
      const assetId = addAsset({ kind: 'comic-script', title, genre: tpl.genre, premise: text || '模板默认', content })
      updateJob(jobId, { status: 'scripted', assetId })

      // R3: 入云渲染队列（幂等键 = 本地任务 id，重试不会重复入队）
      const enq = await cloudEnqueueJob({ templateSlug: tpl.slug, premise: text || '', idempotency: jobId })
      if (enq.ok) {
        updateJob(jobId, { status: 'queued', cloudJobId: enq.data.jobId })
        void message.success(
          enq.data.duplicate
            ? `「${tpl.title}」已在云端队列中（任务 #${enq.data.jobId}）`
            : `「${tpl.title}」分镜脚本已生成并入资产库，已提交云端渲染队列（任务 #${enq.data.jobId}）`,
        )
      } else {
        updateJob(jobId, { status: 'scripted', error: `云端入队失败：${enq.message}` })
        void message.warning(`脚本已生成并入资产库；云端入队失败：${enq.message}`)
      }
    } catch (err) {
      updateJob(jobId, { status: 'failed', error: (err as Error).message })
      void message.error(`生成失败：${(err as Error).message}`)
    } finally {
      setStarting(false)
      setActive(null)
    }
  }

  const copyScript = async (job: RenderJob) => {
    const assets = useAssetStore.getState().assets
    const a = assets.find((x) => x.id === job.assetId)
    if (!a) {
      void message.info('暂无脚本内容')
      return
    }
    try {
      await navigator.clipboard?.writeText(a.content)
      void message.success('已复制脚本到剪贴板')
    } catch {
      void message.info('复制被浏览器拒绝，请使用导出')
    }
  }

  return (
    <div className="h-full overflow-auto px-6 py-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <Typography.Title level={4} className="!text-white !mb-1">漫剧模板</Typography.Title>
          <div className="text-xs text-gray-500 flex items-center gap-2">
            <span>选模板 → 输入梗概 → 一键出片（Agent 生成分镜脚本 → 入资产库 → 提交云端渲染队列）</span>
            <Tooltip title={source === 'cloud' ? '模板来自 /api/comic/templates' : '云端不可达，已回退内置种子模板'}>
              <Tag
                color={source === 'cloud' ? 'blue' : 'default'}
                icon={source === 'cloud' ? <CloudOutlined /> : <CloudDownloadOutlined />}
                style={{ fontSize: 10 }}
              >
                {source === 'cloud' ? '云端模板' : '内置模板'}
              </Tag>
            </Tooltip>
          </div>
        </div>
        <Space size={8}>
          <Button size="small" icon={<SyncOutlined spin={loading} />} onClick={() => void loadTemplates()} disabled={loading}>
            刷新
          </Button>
          <Select size="small" value={genre} onChange={setGenre} options={genres.map((g) => ({ value: g, label: g }))} style={{ width: 110 }} />
        </Space>
      </div>

      <div className="mb-3 max-w-xl">
        <Input
          value={premise}
          onChange={(e) => setPremise(e.target.value)}
          placeholder="故事梗概（一句话，可留空用模板默认题材）…"
          className="!bg-[#11111b] !text-gray-100 !border-[#313244]"
          prefix={<PlayCircleOutlined style={{ color: '#6b7280' }} />}
        />
      </div>

      <div className="grid grid-cols-2 xl:grid-cols-3 gap-3">
        {list.map((t) => (
          <div key={t.slug} className="rounded-lg bg-[#1e1e2e] border border-[#313244] p-3 hover:border-blue-500 transition-colors">
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm text-white font-medium">{t.title}</span>
              <Tag color="default" style={{ fontSize: 10 }}>{t.genre}</Tag>
            </div>
            <div className="text-[11px] text-gray-400 mb-2 min-h-[2.5em]">{t.description}</div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] text-gray-500">{t.shots} 分镜 · {t.priceCredits} 积分</span>
            </div>
            <Button
              size="small"
              type="primary"
              ghost
              icon={<PlayCircleOutlined />}
              loading={starting && active?.slug === t.slug}
              disabled={starting}
              onClick={() => void quickStart(t)}
            >
              一键出片
            </Button>
          </div>
        ))}
      </div>

      {/* 任务卡流 */}
      <div className="mt-6">
        <div className="flex items-center justify-between mb-2">
          <Typography.Text className="!text-gray-300 !text-sm">我的出片任务</Typography.Text>
          <Space size={4}>
            <Button size="small" type="text" icon={<SyncOutlined />} onClick={() => void syncCloud()} className="!text-gray-400">
              同步云端状态
            </Button>
            <Button size="small" type="text" onClick={() => useJobStore.getState().clearDone()} className="!text-gray-500">
              清理已完成
            </Button>
          </Space>
        </div>
        {jobs.length === 0 && <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={<span className="text-xs text-gray-500">暂无任务，选个模板开始</span>} />}
        <div className="flex flex-col gap-2 max-h-72 overflow-auto">
          {jobs.map((j) => {
            const meta = STATUS_META[j.status]
            return (
              <div key={j.id} className="flex items-center gap-3 rounded-lg bg-[#1e1e2e] border border-[#313244] px-3 py-2">
                {j.status === 'drafting' ? <Spin size="small" /> : <span style={{ color: '#fff' }}>{meta.icon}</span>}
                <div className="min-w-0 flex-1">
                  <div className="text-xs text-gray-200 truncate">{j.templateTitle} · {j.premise.slice(0, 30)}</div>
                  <div className="text-[10px] text-gray-500">
                    <Tag color={meta.color} style={{ fontSize: 9, marginRight: 4 }}>{meta.label}</Tag>
                    {new Date(j.createdAt).toLocaleString('zh-CN')}
                    {j.cloudJobId ? ` · 云端 #${j.cloudJobId}` : ''}
                    {j.error ? ` · ${j.error}` : ''}
                  </div>
                </div>
                <Space size={4}>
                  <Button size="small" type="text" icon={<CopyOutlined />} onClick={() => void copyScript(j)} disabled={!j.assetId} title="复制脚本" />
                  <Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={() => removeJob(j.id)} title="删除任务" />
                </Space>
              </div>
            )
          })}
        </div>
      </div>

      {/* R3: 云端成片（服务端渲染 worker 产出，kind=comic-render） */}
      <div className="mt-6 pb-6">
        <div className="flex items-center justify-between mb-2">
          <Typography.Text className="!text-gray-300 !text-sm flex items-center gap-2">
            <PictureOutlined style={{ color: '#60a5fa' }} /> 云端成片
            <span className="text-[11px] text-gray-500">（服务端按队列渲染产出，链接 1 小时有效）</span>
          </Typography.Text>
          <Button size="small" type="text" icon={<SyncOutlined spin={renderLoading} />} className="!text-gray-400" onClick={() => void loadRenders()} disabled={renderLoading}>
            刷新
          </Button>
        </div>
        {renders.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={<span className="text-xs text-gray-500">暂无成片，提交任务后点"同步云端状态"查看进度</span>} />
        ) : (
          <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
            {renders.map((a) => {
              const imgs = renderImages(a)
              return (
                <div key={a.id} className="rounded-lg bg-[#1e1e2e] border border-[#313244] p-2">
                  {imgs[0] ? (
                    <a href={imgs[0]} target="_blank" rel="noreferrer">
                      <img src={imgs[0]} alt={a.title} className="w-full aspect-video object-cover rounded border border-[#313244]" />
                    </a>
                  ) : (
                    <div className="w-full aspect-video rounded bg-[#11111b] border border-[#313244] flex items-center justify-center text-[10px] text-gray-600">
                      无预览
                    </div>
                  )}
                  <div className="mt-1 text-[11px] text-gray-300 truncate">{a.title}</div>
                  <div className="text-[10px] text-gray-500">
                    {a.genre || '—'} · {new Date(a.created_at).toLocaleString('zh-CN')}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
