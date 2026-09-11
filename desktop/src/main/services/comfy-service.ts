/**
 * R4b-1 ComfyUI 本地渲染通道（桌面端直连用户本机 ComfyUI）
 *
 * 定位：桌面端"本地 GPU"渲染路线。用户在自机启动 ComfyUI（默认 127.0.0.1:8188），
 *       桌面端直接提交工作流并取图，不经服务器、不消耗云端算力。
 *
 * 设计对齐既有服务：依赖注入（http/fs），可离线单测；全路径边界处理不抛未捕获异常。
 * 端点契约（ComfyUI 官方 API）：
 *   GET  /system_stats                 探活与设备信息
 *   GET  /object_info/{node}           取节点定义（用 CheckpointLoaderSimple 列可用模型）
 *   POST /prompt                       提交工作流 -> { prompt_id }
 *   GET  /history/{prompt_id}          轮询结果 -> outputs[].images[]
 *   GET  /view?filename=&subfolder=&type=   取图二进制
 */
import path from 'path'

export interface ComfyDevice {
  name: string
  vramTotalMB: number
  vramFreeMB: number
}

export interface ComfyProbeResult {
  available: boolean
  base: string
  version?: string
  devices: ComfyDevice[]
  checkpoints: string[]
  message?: string
}

export interface ComfyRenderInput {
  prompt: string
  negative?: string
  width?: number
  height?: number
  steps?: number
  cfg?: number
  seed?: number
  ckpt?: string
  /** 轮询总超时，默认 10 分钟 */
  timeoutMs?: number
}

export interface ComfyImage {
  filename: string
  subfolder: string
  type: string
  /** 落盘绝对路径（userData/renders/） */
  filePath?: string
  /** base64 data URL，供渲染层直接预览 */
  dataUrl?: string
}

export type ComfyErrorCode = 'offline' | 'no-model' | 'timeout' | 'invalid' | 'network'

export type ComfyRenderResult =
  | { ok: true; promptId: string; elapsedMs: number; images: ComfyImage[] }
  | { ok: false; code: ComfyErrorCode; message: string }

/** 默认工作流模板（SD1.5 base，API 格式）。占位符在提交前替换。 */
export const DEFAULT_TXT2IMG_WORKFLOW: Record<string, { class_type: string; inputs: Record<string, unknown> }> = {
  '3': {
    class_type: 'KSampler',
    inputs: {
      seed: 0,
      steps: 24,
      cfg: 7,
      sampler_name: 'dpmpp_2m',
      scheduler: 'karras',
      denoise: 1,
      model: ['4', 0],
      positive: ['6', 0],
      negative: ['7', 0],
      latent_image: ['5', 0],
    },
  },
  '4': { class_type: 'CheckpointLoaderSimple', inputs: { ckpt_name: '__CKPT__' } },
  '5': { class_type: 'EmptyLatentImage', inputs: { width: 512, height: 512, batch_size: 1 } },
  '6': { class_type: 'CLIPTextEncode', inputs: { text: '__PROMPT__', clip: ['4', 1] } },
  '7': { class_type: 'CLIPTextEncode', inputs: { text: '__NEGATIVE__', clip: ['4', 1] } },
  '8': { class_type: 'VAEDecode', inputs: { samples: ['3', 0], vae: ['4', 2] } },
  '9': { class_type: 'SaveImage', inputs: { filename_prefix: 'YNEX', images: ['8', 0] } },
}

const DEFAULT_NEGATIVE =
  'lowres, bad anatomy, bad hands, text, watermark, signature, blurry, jpeg artifacts, worst quality, low quality'
const DEFAULT_CKPT = 'v1-5-pruned-emaonly.safetensors'
const DEFAULT_TIMEOUT_MS = 10 * 60_000
const POLL_INTERVAL_MS = 2_000

/** /history/{id} 响应结构（仅取用到的字段） */
type ComfyHistory = Record<
  string,
  { outputs?: Record<string, { images?: { filename?: string; subfolder?: string; type?: string }[] }> }
>

type HttpLike = (
  url: string,
  init?: { method?: string; headers?: Record<string, string>; body?: string; signal?: AbortSignal },
) => Promise<{ ok: boolean; status: number; json(): Promise<unknown>; arrayBuffer?(): Promise<ArrayBuffer> }>

interface FsLike {
  writeFileSync(file: string, data: Buffer): void
  mkdirSync(dir: string, opts: { recursive: boolean }): void
  existsSync(p: string): boolean
}

export class ComfyService {
  constructor(
    private readonly base: string,
    private readonly http: HttpLike = (...a) => fetch(...(a as [any, any])) as unknown as ReturnType<HttpLike>,
    private readonly outDir: string = '',
    private readonly fs: FsLike | null = null,
  ) {}

  private url(p: string): string {
    return `${this.base.replace(/\/+$/, '')}${p}`
  }

  /** 探活 + 取设备与可用模型清单 */
  async probe(): Promise<ComfyProbeResult> {
    const result: ComfyProbeResult = { available: false, base: this.base, devices: [], checkpoints: [] }
    try {
      const ctrl = new AbortController()
      const timer = setTimeout(() => ctrl.abort(), 6_000)
      const res = await this.http(this.url('/system_stats'), { signal: ctrl.signal })
      clearTimeout(timer)
      if (!res.ok) {
        result.message = `ComfyUI 返回 ${res.status}`
        return result
      }
      const body = (await res.json().catch(() => null)) as
        | { system?: { comfyui_version?: string }; devices?: { name?: string; vram_total?: number; vram_free?: number }[] }
        | null
      result.available = true
      result.version = body?.system?.comfyui_version
      result.devices = (body?.devices ?? []).map((d) => ({
        name: String(d?.name ?? 'unknown'),
        vramTotalMB: Math.round(Number(d?.vram_total ?? 0) / 1048576),
        vramFreeMB: Math.round(Number(d?.vram_free ?? 0) / 1048576),
      }))
      result.checkpoints = await this.listCheckpoints()
      if (result.checkpoints.length === 0) result.message = 'ComfyUI 已连通，但未检测到任何 checkpoint 模型'
      return result
    } catch (err) {
      const aborted = err instanceof Error && err.name === 'AbortError'
      result.message = aborted ? 'ComfyUI 探活超时' : '无法连接本机 ComfyUI（默认 127.0.0.1:8188）'
      return result
    }
  }

  /** 列出 checkpoint 模型（走 object_info，不依赖文件系统） */
  async listCheckpoints(): Promise<string[]> {
    try {
      const ctrl = new AbortController()
      const timer = setTimeout(() => ctrl.abort(), 8_000)
      const res = await this.http(this.url('/object_info/CheckpointLoaderSimple'), { signal: ctrl.signal })
      clearTimeout(timer)
      if (!res.ok) return []
      const body = (await res.json().catch(() => null)) as
        | Record<string, { input?: { required?: { ckpt_name?: unknown[] } } }>
        | null
      const list = body?.CheckpointLoaderSimple?.input?.required?.ckpt_name?.[0]
      return Array.isArray(list) ? list.map(String) : []
    } catch {
      return []
    }
  }

  /** 用输入参数渲染出图（提交 -> 轮询 -> 取图落盘） */
  async render(input: ComfyRenderInput): Promise<ComfyRenderResult> {
    const prompt = String(input.prompt || '').trim()
    if (!prompt) return { ok: false, code: 'invalid', message: '提示词为空' }

    const checkpoints = await this.listCheckpoints()
    if (checkpoints.length === 0) {
      return { ok: false, code: 'no-model', message: '本机 ComfyUI 未安装任何 checkpoint 模型，请先放置模型到 models/checkpoints' }
    }
    const ckpt = input.ckpt && checkpoints.includes(input.ckpt) ? input.ckpt : checkpoints[0]

    const started = Date.now()
    let promptId = ''
    try {
      const graph = buildWorkflow({ ...input, prompt, ckpt })
      const ctrl = new AbortController()
      const timer = setTimeout(() => ctrl.abort(), 30_000)
      const res = await this.http(this.url('/prompt'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: graph, client_id: 'ynex-studio' }),
        signal: ctrl.signal,
      })
      clearTimeout(timer)
      if (!res.ok) {
        const detail = await res.json().catch(() => null)
        return { ok: false, code: 'invalid', message: `工作流提交失败(${res.status})：${formatNodeError(detail)}` }
      }
      const sub = (await res.json().catch(() => null)) as { prompt_id?: string } | null
      promptId = String(sub?.prompt_id || '')
      if (!promptId) return { ok: false, code: 'invalid', message: 'ComfyUI 未返回 prompt_id' }
    } catch (err) {
      const aborted = err instanceof Error && err.name === 'AbortError'
      return { ok: false, code: aborted ? 'timeout' : 'offline', message: aborted ? '提交工作流超时' : '无法连接本机 ComfyUI' }
    }

    // 轮询结果
    const deadline = Date.now() + (input.timeoutMs ?? DEFAULT_TIMEOUT_MS)
    while (Date.now() < deadline) {
      await sleep(POLL_INTERVAL_MS)
      let hist: ComfyHistory | null = null
      try {
        const ctrl = new AbortController()
        const timer = setTimeout(() => ctrl.abort(), 15_000)
        const res = await this.http(this.url(`/history/${promptId}`), { signal: ctrl.signal })
        clearTimeout(timer)
        if (res.ok) hist = (await res.json().catch(() => null)) as ComfyHistory | null
      } catch {
        /* 单次轮询失败继续重试 */
      }
      const entry = hist?.[promptId]
      if (!entry) continue
      const images: ComfyImage[] = []
      for (const node of Object.values(entry.outputs ?? {}) as { images?: { filename?: string; subfolder?: string; type?: string }[] }[]) {
        for (const img of node.images ?? []) {
          if (img?.filename) images.push({ filename: img.filename, subfolder: img.subfolder ?? '', type: img.type ?? 'output' })
        }
      }
      if (images.length === 0) continue
      const saved = await this.fetchImages(images)
      return { ok: true, promptId, elapsedMs: Date.now() - started, images: saved }
    }
    return { ok: false, code: 'timeout', message: `渲染超时（${Math.round((input.timeoutMs ?? DEFAULT_TIMEOUT_MS) / 1000)}s）` }
  }

  /** 取图并落盘 + 生成预览 dataUrl */
  private async fetchImages(images: ComfyImage[]): Promise<ComfyImage[]> {
    const out: ComfyImage[] = []
    for (const img of images) {
      const q = `filename=${encodeURIComponent(img.filename)}&subfolder=${encodeURIComponent(img.subfolder)}&type=${encodeURIComponent(img.type)}`
      try {
        const ctrl = new AbortController()
        const timer = setTimeout(() => ctrl.abort(), 30_000)
        const res = await this.http(this.url(`/view?${q}`), { signal: ctrl.signal })
        clearTimeout(timer)
        if (!res.ok || !res.arrayBuffer) {
          out.push(img)
          continue
        }
        const buf = Buffer.from(await res.arrayBuffer())
        const item: ComfyImage = { ...img }
        if (this.fs && this.outDir) {
          try {
            this.fs.mkdirSync(this.outDir, { recursive: true })
            const file = path.join(this.outDir, `${Date.now()}_${img.filename.replace(/[^\w.-]/g, '_')}`)
            this.fs.writeFileSync(file, buf)
            item.filePath = file
          } catch {
            /* 落盘失败不阻断：仍有 dataUrl */
          }
        }
        item.dataUrl = `data:image/png;base64,${buf.toString('base64')}`
        out.push(item)
      } catch {
        out.push(img)
      }
    }
    return out
  }
}

/** 注入占位符生成可提交的工作流图 */
export function buildWorkflow(
  input: ComfyRenderInput & { ckpt: string },
): Record<string, { class_type: string; inputs: Record<string, unknown> }> {
  const graph = JSON.parse(JSON.stringify(DEFAULT_TXT2IMG_WORKFLOW)) as typeof DEFAULT_TXT2IMG_WORKFLOW
  const seed = Number.isFinite(input.seed) ? Number(input.seed) : Math.floor(Math.random() * 2 ** 31)
  graph['3'].inputs.seed = seed
  graph['3'].inputs.steps = clamp(Number(input.steps) || 24, 1, 60)
  graph['3'].inputs.cfg = clamp(Number(input.cfg) || 7, 1, 20)
  graph['5'].inputs.width = clamp(Number(input.width) || 512, 256, 1536)
  graph['5'].inputs.height = clamp(Number(input.height) || 512, 256, 1536)
  graph['4'].inputs.ckpt_name = input.ckpt
  graph['6'].inputs.text = input.prompt
  graph['7'].inputs.text = String(input.negative || DEFAULT_NEGATIVE)
  return graph
}

export const COMFY_DEFAULTS = {
  base: 'http://127.0.0.1:8188',
  ckpt: DEFAULT_CKPT,
  negative: DEFAULT_NEGATIVE,
  timeoutMs: DEFAULT_TIMEOUT_MS,
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, Math.round(v)))
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms))
}

/** 从 /prompt 的错误体里提取人话（ComfyUI 返回 node_errors 结构） */
function formatNodeError(detail: unknown): string {
  try {
    const d = detail as { error?: { message?: string; details?: string }; node_errors?: Record<string, { errors?: { message?: string }[] }> }
    if (d?.error?.message) return String(d.error.message)
    const nodeErr = d?.node_errors && Object.values(d.node_errors)[0]
    const msg = nodeErr?.errors?.[0]?.message
    if (msg) return String(msg)
    return JSON.stringify(detail).slice(0, 200)
  } catch {
    return '未知错误'
  }
}

/** electron 环境工厂 */
export function createComfyService(outDir: string): ComfyService {
  let fsImpl: FsLike | null = null
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    fsImpl = require('fs') as FsLike
  } catch {
    fsImpl = null
  }
  return new ComfyService(process.env.YNEX_COMFY_BASE || COMFY_DEFAULTS.base, undefined, outDir, fsImpl)
}
