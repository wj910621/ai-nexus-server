/**
 * P3 agent-service 单元测试
 * 覆盖：未登录/空消息/非法模型/成功/401/积分不足(quota 识别)/网络/超时/空返回/model alias
 */
import { describe, it, expect, vi } from 'vitest'
import type { AgentResult } from '@shared/types'
import { AgentService } from '../main/services/agent-service'

const BASE = 'https://ynexai.cn'

function okJson(status: number, body: unknown): { ok: boolean; status: number; json(): Promise<unknown> } {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}

function svc(token: string | null = 'tok', http?: unknown): AgentService {
  return new AgentService(() => token, BASE, (http as never) ?? (async () => okJson(200, { choices: [{ message: { content: 'hi' } }] })))
}

describe('AgentService.chat', () => {
  it('未登录 -> unauthorized', async () => {
    const r = (await svc(null).chat([{ role: 'user', content: 'a' }], { model: 'deepseek-chat' })) as AgentResult
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.code).toBe('unauthorized')
  })

  it('空消息 -> invalid', async () => {
    const r = (await svc().chat([], { model: 'deepseek-chat' })) as AgentResult
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.code).toBe('invalid')
  })

  it('空 model -> invalid', async () => {
    const r = (await svc().chat([{ role: 'user', content: 'x' }], { model: '' })) as AgentResult
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.code).toBe('invalid')
  })

  it('成功返回 content', async () => {
    const s = svc('t', async (u: string, init?: { body?: string }) => {
      const body = JSON.parse(init?.body ?? '{}')
      expect(body.model).toBe('deepseek/deepseek-chat') // alias 解析
      expect(u).toBe(`${BASE}/v1/chat/completions`)
      return okJson(200, { choices: [{ message: { content: '你好' } }] })
    })
    const r = await s.chat([{ role: 'user', content: 'hi' }], { model: 'deepseek-chat' })
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.content).toBe('你好')
  })

  it('401 -> unauthorized', async () => {
    const s = svc('expired', async () => okJson(401, { error: { message: 'x' } }))
    const r = await s.chat([{ role: 'user', content: 'a' }], { model: 'deepseek-chat' })
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.code).toBe('unauthorized')
  })

  it('quota/余额不足 -> quota', async () => {
    const s = svc('t', async () => okJson(402, { error: { message: 'insufficient credits 余额不足' } }))
    const r = await s.chat([{ role: 'user', content: 'a' }], { model: 'deepseek-chat' })
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.code).toBe('quota')
  })

  it('网络异常 -> network', async () => {
    const s = svc('t', async () => { throw new TypeError('down') })
    const r = await s.chat([{ role: 'user', content: 'a' }], { model: 'deepseek-chat' })
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.code).toBe('network')
  })

  it('AbortError -> network(超时)', async () => {
    const s = svc('t', async () => { throw new DOMException('Aborted', 'AbortError') })
    const r = await s.chat([{ role: 'user', content: 'a' }], { model: 'deepseek-chat' })
    expect(r.ok).toBe(false)
    if (!r.ok) {
      expect(r.code).toBe('network')
      expect(r.message).toContain('超时')
    }
  })

  it('空返回 -> invalid', async () => {
    const s = svc('t', async () => okJson(200, { choices: [{ message: { content: '' } }] }))
    const r = await s.chat([{ role: 'user', content: 'a' }], { model: 'deepseek-chat' })
    expect(r.ok).toBe(false)
  })
})

describe('AgentService.createComicScript', () => {
  it('组装分镜 prompt 并成功', async () => {
    const s = new AgentService(
      () => 't',
      BASE,
      (async (_u: string, init?: { body?: string }) => {
        const body = JSON.parse(init?.body ?? '{}')
        expect(body.messages[0].content).toContain('资深漫剧编剧')
        expect(body.messages[0].content).toContain('科幻')
        return okJson(200, { choices: [{ message: { content: '{"title":"测试"}' } }] })
      }) as never,
    )
    const r = await s.createComicScript('外星人入侵', '科幻')
    expect(r.ok).toBe(true)
  })
})
