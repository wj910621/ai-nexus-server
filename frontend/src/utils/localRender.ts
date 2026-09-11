/**
 * R4b-1 本机 ComfyUI 渲染桥（桌面端 IPC；浏览器环境不可用）
 * 与 cloud.ts 的云渲染通道并列，共同构成"双通道渲染"：
 *   - 云端（cloud.ts）  ：服务端 provider，按张计费，无需本地 GPU
 *   - 本机（本文件）    ：用户自机 ComfyUI，零算力成本，需本地 GPU + 模型
 */
import { isDesktop } from './mainAccount'

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
}

export interface ComfyImage {
  filename: string
  subfolder: string
  type: string
  filePath?: string
  dataUrl?: string
}

export type ComfyRenderResult =
  | { ok: true; promptId: string; elapsedMs: number; images: ComfyImage[] }
  | { ok: false; code: string; message: string }

/** 本机渲染通道是否可用（桌面端且 preload 已就绪） */
export function hasLocalRender(): boolean {
  return isDesktop() && !!window.electronAPI?.render
}

export async function probeComfy(): Promise<ComfyProbeResult> {
  const api = window.electronAPI?.render
  if (!api) {
    return { available: false, base: '', devices: [], checkpoints: [], message: '当前非桌面端环境，本机渲染不可用' }
  }
  return (await api.comfyProbe()) as ComfyProbeResult
}

export async function runComfy(input: ComfyRenderInput): Promise<ComfyRenderResult> {
  const api = window.electronAPI?.render
  if (!api) return { ok: false, code: 'offline', message: '当前非桌面端环境，本机渲染不可用' }
  return (await api.comfyRun(input)) as ComfyRenderResult
}

/** 从分镜对象提取画面提示词（与服务端 shotPrompt 保持同一套字段优先级） */
export function shotPrompt(s: unknown): string {
  const o = (s ?? {}) as Record<string, unknown>
  const v = o.scene_prompt ?? o.prompt ?? o.description ?? o.content ?? o.scene
  return typeof v === 'string' ? v : ''
}

/** 从漫剧脚本 JSON 提取分镜数组（R4b-2）。非 JSON 或空则返回空数组。 */
export function shotsFromScript(script: string): { prompt: string }[] {
  try {
    const obj = JSON.parse(script) as { shots?: unknown[] }
    if (!Array.isArray(obj.shots)) return []
    return obj.shots
      .map((s) => ({ prompt: shotPrompt(s) }))
      .filter((s) => s.prompt)
  } catch {
    return []
  }
}

/** 由漫剧脚本 JSON 提取首镜出图提示词（回退 title / 原文截断） */
export function promptFromScript(script: string): string {
  const shots = shotsFromScript(script)
  if (shots.length) return shots[0].prompt
  try {
    const obj = JSON.parse(script) as { title?: string }
    if (obj.title) return String(obj.title)
  } catch {
    /* 非 JSON：截断原文 */
  }
  return script.slice(0, 300)
}
