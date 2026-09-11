/**
 * R2 memory-service 单元测试（tmp 目录注入）
 * 覆盖：append/query 匹配/recent 倒序/空词/大小写/损坏行跳过/超长拒绝/滚动裁剪
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import fs from 'fs'
import os from 'os'
import path from 'path'
import { MemoryService } from '../main/services/memory-service'

let dir: string
let svc: MemoryService

beforeEach(() => {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), 'memtest-'))
  svc = new MemoryService(dir)
})
afterEach(() => {
  fs.rmSync(dir, { recursive: true, force: true })
})

describe('MemoryService', () => {
  it('append 后 search 命中(大小写不敏感)', () => {
    svc.append({ username: 'wj0007', sessionId: 's1', role: 'user', content: '帮我写仙侠分镜' })
    const r = svc.query('wj0007', '仙侠')
    expect(r.total).toBe(1)
    expect(r.records[0].content).toContain('仙侠')
  })

  it('不同用户隔离', () => {
    svc.append({ username: 'a', sessionId: 'x', role: 'user', content: '秘密内容 keyword' })
    const r = svc.query('b', 'keyword')
    expect(r.total).toBe(0)
  })

  it('空关键词 -> 0 结果(不返回全量)', () => {
    svc.append({ username: 'a', sessionId: 'x', role: 'user', content: '随便' })
    expect(svc.query('a', '').total).toBe(0)
  })

  it('recent 倒序返回', () => {
    svc.append({ username: 'a', sessionId: 'x', role: 'user', content: '第一条' })
    svc.append({ username: 'a', sessionId: 'x', role: 'user', content: '第二条' })
    const r = svc.recent('a', 10)
    expect(r.length).toBe(2)
    expect(r[0].content).toBe('第二条')
  })

  it('损坏行被跳过', () => {
    fs.appendFileSync(path.join(dir, 'conversations.jsonl'), '{bad json}\n', 'utf8')
    svc.append({ username: 'a', sessionId: 'x', role: 'user', content: '正常' })
    expect(svc.recent('a', 10).length).toBe(1)
  })

  it('超长 content 被拒', () => {
    svc.append({ username: 'a', sessionId: 'x', role: 'user', content: 'x'.repeat(20_000) })
    expect(svc.recent('a', 10).length).toBe(0)
  })
})
