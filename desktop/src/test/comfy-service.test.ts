/**
 * R4b-1 comfy-service 单元测试
 * 覆盖：探活(在线/离线/超时)、模型清单、渲染全链路(提交→轮询→取图)、
 *       无模型、空提示词、提交失败、工作流占位符注入与参数钳制
 */
import { describe, it, expect, vi } from 'vitest'
import { ComfyService, buildWorkflow, COMFY_DEFAULTS } from '../main/services/comfy-service'

const BASE = 'http://127.0.0.1:8188'

type Res = { ok: boolean; status: number; json(): Promise<unknown>; arrayBuffer?(): Promise<ArrayBuffer> }

function jsonRes(status: number, body: unknown): Res {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}
function binRes(bytes = [1, 2, 3]): Res {
  return {
    ok: true,
    status: 200,
    json: async () => ({}),
    arrayBuffer: async () => new Uint8Array(bytes).buffer,
  }
}

/** 按 URL 路由的 http 替身 */
function router(handlers: Record<string, () => Res | Promise<Res>>) {
  return vi.fn(async (url: string) => {
    for (const [key, fn] of Object.entries(handlers)) {
      if (url.includes(key)) return fn()
    }
    throw new Error(`unrouted: ${url}`)
  })
}

describe('ComfyService.probe', () => {
  it('在线：返回版本/设备/模型清单', async () => {
    const http = router({
      '/system_stats': () =>
        jsonRes(200, {
          system: { comfyui_version: '0.3.70' },
          devices: [{ name: 'cuda:0 NVIDIA GeForce RTX 5070 Laptop GPU', vram_total: 8 * 1048576 * 1024, vram_free: 7 * 1048576 * 1024 }],
        }),
      '/object_info/CheckpointLoaderSimple': () => jsonRes(200, { CheckpointLoaderSimple: { input: { required: { ckpt_name: [['a.safetensors']] } } } }),
    })
    const s = new ComfyService(BASE, http as never)
    const r = await s.probe()
    expect(r.available).toBe(true)
    expect(r.version).toBe('0.3.70')
    expect(r.devices[0].vramTotalMB).toBe(8192)
    expect(r.checkpoints).toEqual(['a.safetensors'])
  })

  it('连通但无模型 -> 可用 + 提示语', async () => {
    const http = router({
      '/system_stats': () => jsonRes(200, { system: {}, devices: [] }),
      '/object_info/CheckpointLoaderSimple': () => jsonRes(200, { CheckpointLoaderSimple: { input: { required: { ckpt_name: [[]] } } } }),
    })
    const s = new ComfyService(BASE, http as never)
    const r = await s.probe()
    expect(r.available).toBe(true)
    expect(r.checkpoints).toEqual([])
    expect(r.message).toContain('未检测到')
  })

  it('离线 -> available false + 提示', async () => {
    const http = vi.fn(async () => { throw new TypeError('ECONNREFUSED') })
    const s = new ComfyService(BASE, http as never)
    const r = await s.probe()
    expect(r.available).toBe(false)
    expect(r.message).toContain('无法连接')
  })

  it('探活超时 -> 提示超时', async () => {
    const http = vi.fn(async () => { throw new DOMException('Aborted', 'AbortError') })
    const s = new ComfyService(BASE, http as never)
    const r = await s.probe()
    expect(r.available).toBe(false)
    expect(r.message).toContain('超时')
  })
})

describe('ComfyService.render 前置校验', () => {
  it('空提示词 -> invalid 且不发请求', async () => {
    const http = vi.fn(async () => jsonRes(200, {}))
    const s = new ComfyService(BASE, http as never)
    const r = await s.render({ prompt: '   ' })
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.code).toBe('invalid')
    expect(http).not.toHaveBeenCalled()
  })

  it('无 checkpoint -> no-model', async () => {
    const http = router({ '/object_info/CheckpointLoaderSimple': () => jsonRes(200, { CheckpointLoaderSimple: { input: { required: { ckpt_name: [[]] } } } }) })
    const s = new ComfyService(BASE, http as never)
    const r = await s.render({ prompt: 'a cat' })
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.code).toBe('no-model')
  })
})

describe('ComfyService.render 全链路', () => {
  it('提交-轮询-取图成功', async () => {
    let historyCalls = 0
    const http = router({
      '/object_info/CheckpointLoaderSimple': () => jsonRes(200, { CheckpointLoaderSimple: { input: { required: { ckpt_name: [['v1-5-pruned-emaonly.safetensors']] } } } }),
      '/prompt': () => jsonRes(200, { prompt_id: 'pid-1' }),
      '/history/pid-1': () => {
        historyCalls += 1
        return jsonRes(200, historyCalls < 2 ? {} : { 'pid-1': { outputs: { '9': { images: [{ filename: 'YNEX_00001_.png', subfolder: '', type: 'output' }] } } } })
      },
      '/view?': () => binRes([137, 80, 78, 71]),
    })
    const s = new ComfyService(BASE, http as never)
    const r = await s.render({ prompt: 'a cat', seed: 42, timeoutMs: 20_000 })
    expect(r.ok).toBe(true)
    if (r.ok) {
      expect(r.promptId).toBe('pid-1')
      expect(r.images).toHaveLength(1)
      expect(r.images[0].filename).toBe('YNEX_00001_.png')
      expect(r.images[0].dataUrl).toMatch(/^data:image\/png;base64,/)
    }
  }, 30_000)

  it('提交失败 -> invalid 带服务端错误', async () => {
    const http = router({
      '/object_info/CheckpointLoaderSimple': () => jsonRes(200, { CheckpointLoaderSimple: { input: { required: { ckpt_name: [['x.safetensors']] } } } }),
      '/prompt': () => jsonRes(400, { error: { message: 'Prompt outputs failed validation' } }),
    })
    const s = new ComfyService(BASE, http as never)
    const r = await s.render({ prompt: 'a cat' })
    expect(r.ok).toBe(false)
    if (!r.ok) {
      expect(r.code).toBe('invalid')
      expect(r.message).toContain('Prompt outputs failed validation')
    }
  })

  it('提交阶段断连 -> offline', async () => {
    const http = vi.fn(async (url: string) => {
      if (url.includes('/object_info/')) return jsonRes(200, { CheckpointLoaderSimple: { input: { required: { ckpt_name: [['x.safetensors']] } } } })
      throw new TypeError('ECONNREFUSED')
    })
    const s = new ComfyService(BASE, http as never)
    const r = await s.render({ prompt: 'a cat' })
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.code).toBe('offline')
  })
})

describe('buildWorkflow 模板注入', () => {
  const wf = buildWorkflow({ prompt: 'a hero', ckpt: 'm.safetensors', seed: 7, width: 768, height: 432, steps: 30, cfg: 8 })

  it('占位符全部替换', () => {
    expect(wf['4'].inputs.ckpt_name).toBe('m.safetensors')
    expect(wf['6'].inputs.text).toBe('a hero')
    expect(String(wf['7'].inputs.text)).toContain('lowres')
    expect(wf['3'].inputs.seed).toBe(7)
    expect(wf['5'].inputs.width).toBe(768)
    expect(wf['5'].inputs.height).toBe(432)
    expect(wf['3'].inputs.steps).toBe(30)
    expect(wf['3'].inputs.cfg).toBe(8)
  })

  it('参数钳制生效（超界回落到边界）', () => {
    const w = buildWorkflow({ prompt: 'x', ckpt: 'c', width: 99, height: 99999, steps: 999, cfg: 999 })
    expect(w['5'].inputs.width).toBe(256)
    expect(w['5'].inputs.height).toBe(1536)
    expect(w['3'].inputs.steps).toBe(60)
    expect(w['3'].inputs.cfg).toBe(20)
  })

  it('0/NaN 等 falsy 参数回落到默认值', () => {
    const w = buildWorkflow({ prompt: 'x', ckpt: 'c', cfg: 0, steps: 0, width: 0, height: 0 })
    expect(w['3'].inputs.cfg).toBe(7)
    expect(w['3'].inputs.steps).toBe(24)
    expect(w['5'].inputs.width).toBe(512)
    expect(w['5'].inputs.height).toBe(512)
  })

  it('未指定 seed 时自动随机', () => {
    const w = buildWorkflow({ prompt: 'x', ckpt: 'c' })
    expect(typeof w['3'].inputs.seed).toBe('number')
  })

  it('自定义负向词生效', () => {
    const w = buildWorkflow({ prompt: 'x', ckpt: 'c', negative: 'blurry' })
    expect(w['7'].inputs.text).toBe('blurry')
  })

  it('默认基址为 127.0.0.1:8188', () => {
    expect(COMFY_DEFAULTS.base).toBe('http://127.0.0.1:8188')
  })
})
