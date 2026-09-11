/**
 * R4b-4 ComfyUI 工作流 ⇄ 画布 转换器测试
 * 覆盖：往返一致性、连线识别、参数保留、非法输入校验、导出包形态兼容
 */
import { describe, it, expect } from 'vitest'
import {
  canvasToComfy,
  comfyToCanvas,
  parseComfyJson,
  validateComfyGraph,
  stringifyComfy,
  type ComfyGraph,
} from '@/utils/comfyGraph'

const GRAPH: ComfyGraph = {
  '3': {
    class_type: 'KSampler',
    inputs: { seed: 1, steps: 20, model: ['4', 0], positive: ['6', 0], negative: ['7', 0], latent_image: ['5', 0] },
  },
  '4': { class_type: 'CheckpointLoaderSimple', inputs: { ckpt_name: 'a.safetensors' } },
  '5': { class_type: 'EmptyLatentImage', inputs: { width: 512, height: 512, batch_size: 1 } },
  '6': { class_type: 'CLIPTextEncode', inputs: { text: 'hero', clip: ['4', 1] } },
  '7': { class_type: 'CLIPTextEncode', inputs: { text: 'bad', clip: ['4', 1] } },
  '8': { class_type: 'VAEDecode', inputs: { samples: ['3', 0], vae: ['4', 2] } },
  '9': { class_type: 'SaveImage', inputs: { filename_prefix: 'YNEX', images: ['8', 0] } },
}

describe('comfyToCanvas', () => {
  const { nodes, edges } = comfyToCanvas(GRAPH)

  it('节点数一致且保留 class_type', () => {
    expect(nodes).toHaveLength(7)
    const ks = nodes.find((n) => n.id === '3')
    expect((ks?.data as { classType: string }).classType).toBe('KSampler')
  })

  it('连线按 [nodeId, idx] 还原（9 条有向边）', () => {
    expect(edges).toHaveLength(9)
    const toKs = edges.filter((e) => e.target === '3')
    expect(toKs.map((e) => e.targetHandle).sort()).toEqual(['latent_image', 'model', 'negative', 'positive'])
  })

  it('非连线参数进入 data.params（seed/steps/文本等）', () => {
    const ks = nodes.find((n) => n.id === '3')
    const params = (ks?.data as { params: Record<string, unknown> }).params
    expect(params.seed).toBe(1)
    expect(params.steps).toBe(20)
    expect(params.model).toBeUndefined()
  })

  it('节点按类型映射到画布节点类型', () => {
    expect(nodes.find((n) => n.id === '9')?.type).toBe('image_preview')
    expect(nodes.find((n) => n.id === '3')?.type).toBe('imageGen')
  })

  it('自动布局给出不同坐标', () => {
    const xs = new Set(nodes.map((n) => n.position.x))
    expect(xs.size).toBeGreaterThan(1)
  })
})

describe('canvasToComfy 往返', () => {
  it('画布 → 图 往返后结构等价', () => {
    const { nodes, edges } = comfyToCanvas(GRAPH)
    const back = canvasToComfy(nodes, edges)
    expect(Object.keys(back).sort()).toEqual(Object.keys(GRAPH).sort())
    expect(back['4'].class_type).toBe('CheckpointLoaderSimple')
    expect(back['9'].inputs.filename_prefix).toBe('YNEX')
  })

  it('连线写回为 [source, idx] 引用', () => {
    const { nodes, edges } = comfyToCanvas(GRAPH)
    const back = canvasToComfy(nodes, edges)
    expect(back['8'].inputs.samples).toEqual(['3', 0])
    expect(back['8'].inputs.vae).toEqual(['4', 2])
  })

  it('无 classType 时按画布节点类型回退', () => {
    const g = canvasToComfy(
      [{ id: 'n1', type: 'imageGen', position: { x: 0, y: 0 }, data: {} }] as never,
      [],
    )
    expect(g['n1'].class_type).toBe('KSampler')
  })

  it('空画布导出为空对象', () => {
    expect(canvasToComfy([], [])).toEqual({})
  })
})

describe('校验与解析', () => {
  it('validateComfyGraph 接受合法图', () => {
    expect(validateComfyGraph(GRAPH).ok).toBe(true)
  })

  it('拒绝非对象 / 空对象 / 缺 class_type', () => {
    expect(validateComfyGraph(null).ok).toBe(false)
    expect(validateComfyGraph([]).ok).toBe(false)
    expect(validateComfyGraph({}).ok).toBe(false)
    expect(validateComfyGraph({ '1': {} }).ok).toBe(false)
    expect(validateComfyGraph({ '1': { inputs: {} } }).ok).toBe(false)
  })

  it('parseComfyJson 解析直连形态', () => {
    const r = parseComfyJson(stringifyComfy(GRAPH))
    expect(r.ok).toBe(true)
    if (r.ok) expect(Object.keys(r.graph)).toHaveLength(7)
  })

  it('parseComfyJson 兼容 { prompt: {...} } 导出包形态', () => {
    const r = parseComfyJson(JSON.stringify({ prompt: GRAPH }))
    expect(r.ok).toBe(true)
    if (r.ok) expect(Object.keys(r.graph)).toHaveLength(7)
  })

  it('parseComfyJson 对坏 JSON 给出可读错误', () => {
    const r = parseComfyJson('{ not json')
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.message).toContain('JSON 解析失败')
  })

  it('stringifyComfy 产出可被 JSON.parse 回读', () => {
    expect(JSON.parse(stringifyComfy(GRAPH))['3'].class_type).toBe('KSampler')
  })
})
