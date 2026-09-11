/**
 * R4b-4 ComfyUI 工作流 ⇄ React Flow 画布 双向转换
 *
 * ComfyUI API 格式（提交给 POST /prompt 的形态）：
 *   { "<nodeId>": { class_type: "KSampler", inputs: { seed: 0, model: ["4", 0] } }, ... }
 *   其中 inputs 里形如 [nodeId, outputIndex] 的值表示"连线上游节点"。
 *
 * 画布格式（本应用 editorStore）：
 *   nodes: { id, type, position, data }
 *   edges: { id, source, target, sourceHandle?, targetHandle? }
 *
 * 约定：ComfyUI 的节点 id 直接作为画布 node.id；连线落在 targetHandle = 输入名。
 */
import type { WorkflowNode, WorkflowEdge } from '@/types'

export interface ComfyNode {
  class_type: string
  inputs: Record<string, unknown>
}
export type ComfyGraph = Record<string, ComfyNode>

/** ComfyUI class_type → 画布节点类型（未识别则回退 default） */
const CLASS_TO_TYPE: Record<string, string> = {
  CheckpointLoaderSimple: 'text_input',
  CLIPTextEncode: 'text_input',
  EmptyLatentImage: 'text_input',
  KSampler: 'imageGen',
  VAEDecode: 'image_preview',
  SaveImage: 'image_preview',
  LoadImage: 'text_input',
  PreviewImage: 'image_preview',
  LoraLoader: 'character',
  ControlNetApply: 'character',
  TTSNode: 'tts',
  VHS_VideoCombine: 'video_compose',
  TextConcat: 'text_concat',
}

/** 画布节点类型 → ComfyUI class_type（导出时的默认映射） */
const TYPE_TO_CLASS: Record<string, string> = {
  imageGen: 'KSampler',
  text_to_image: 'KSampler',
  text_input: 'CLIPTextEncode',
  text_concat: 'TextConcat',
  character: 'LoraLoader',
  character_gen: 'LoraLoader',
  llm_chat: 'CLIPTextEncode',
  tts: 'TTSNode',
  video_compose: 'VHS_VideoCombine',
  image_preview: 'PreviewImage',
}

function isLink(v: unknown): v is [string, number] {
  return Array.isArray(v) && v.length === 2 && typeof v[0] === 'string' && typeof v[1] === 'number'
}

function makeId(prefix: string, n: number): string {
  return `${prefix}${n}`
}

/** ComfyUI 图 → 画布（简单网格自动布局） */
export function comfyToCanvas(graph: ComfyGraph): { nodes: WorkflowNode[]; edges: WorkflowEdge[] } {
  const nodes: WorkflowNode[] = []
  const edges: WorkflowEdge[] = []
  const ids = Object.keys(graph || {})
  const COLS = 4
  const DX = 240
  const DY = 140

  ids.forEach((id, i) => {
    const n = graph[id]
    const params: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(n?.inputs ?? {})) {
      if (isLink(v)) {
        edges.push({
          id: `e_${v[0]}_${id}_${k}`,
          source: v[0],
          target: id,
          sourceHandle: `out${v[1]}`,
          targetHandle: k,
        })
      } else {
        params[k] = v
      }
    }
    nodes.push({
      id,
      type: CLASS_TO_TYPE[n?.class_type] ?? 'text_input',
      position: { x: 80 + (i % COLS) * DX, y: 80 + Math.floor(i / COLS) * DY },
      data: { label: n?.class_type ?? id, classType: n?.class_type ?? '', params },
    })
  })

  return { nodes, edges }
}

/** 画布 → ComfyUI 图 */
export function canvasToComfy(nodes: WorkflowNode[], edges: WorkflowEdge[]): ComfyGraph {
  const graph: ComfyGraph = {}
  for (const n of nodes) {
    const d = (n.data ?? {}) as { classType?: string; params?: Record<string, unknown> }
    const classType = d.classType || TYPE_TO_CLASS[n.type] || 'CLIPTextEncode'
    graph[n.id] = { class_type: classType, inputs: { ...(d.params ?? {}) } }
  }
  for (const e of edges) {
    const target = graph[e.target]
    if (!target) continue
    const key = e.targetHandle || 'input'
    const outIdx = Number(String(e.sourceHandle ?? 'out0').replace(/\D/g, '')) || 0
    target.inputs[key] = [e.source, outIdx]
  }
  return graph
}

/** 校验是否为可提交的 ComfyUI 图 */
export function validateComfyGraph(obj: unknown): { ok: true; graph: ComfyGraph } | { ok: false; message: string } {
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return { ok: false, message: '不是对象' }
  const entries = Object.entries(obj as Record<string, unknown>)
  if (entries.length === 0) return { ok: false, message: '图内无节点' }
  for (const [id, v] of entries) {
    if (!v || typeof v !== 'object') return { ok: false, message: `节点 ${id} 不是对象` }
    const ct = (v as { class_type?: unknown }).class_type
    if (typeof ct !== 'string' || !ct) return { ok: false, message: `节点 ${id} 缺少 class_type` }
  }
  return { ok: true, graph: obj as ComfyGraph }
}

/** 解析用户粘贴/上传的 JSON 文本 */
export function parseComfyJson(text: string): { ok: true; graph: ComfyGraph } | { ok: false; message: string } {
  let obj: unknown
  try {
    obj = JSON.parse(text)
  } catch (e) {
    return { ok: false, message: `JSON 解析失败：${(e as Error).message}` }
  }
  // 兼容导出包形态 { prompt: {...} }（ComfyUI 保存的 workflow-in-API 变体）
  const maybe = (obj as { prompt?: unknown })?.prompt
  const target = maybe && typeof maybe === 'object' ? maybe : obj
  const v = validateComfyGraph(target)
  if (!v.ok) return { ok: false, message: `不是有效的 ComfyUI 工作流：${v.message}` }
  return { ok: true, graph: v.graph }
}

/** 导出为可提交的 JSON 文本 */
export function stringifyComfy(graph: ComfyGraph): string {
  return JSON.stringify(graph, null, 2)
}

export { makeId }
