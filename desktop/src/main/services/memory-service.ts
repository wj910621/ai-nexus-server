/**
 * R2 记忆系统 v1 — 跨会话记忆服务（本地 JSONL，零原生依赖）
 *  - append/query/clear；滚动上限 5000 条；搜索 = 内容包含匹配（v1 不引向量）
 *  - 存储目录 userData/memory/；文件句柄为追加写，线程安全靠 Node 事件循环串行
 */
import fs from 'fs'
import path from 'path'

export interface MemoryRecord {
  ts: number
  username: string
  sessionId: string
  role: 'user' | 'assistant' | 'system'
  content: string
}

export interface MemorySearchResult {
  records: MemoryRecord[]
  total: number
}

const MAX_ROWS = 5000

export class MemoryService {
  private readonly file: string

  constructor(private readonly baseDir: string) {
    this.file = path.join(baseDir, 'conversations.jsonl')
    this.ensure()
  }

  private ensure(): void {
    try {
      fs.mkdirSync(this.baseDir, { recursive: true })
      if (!fs.existsSync(this.file)) fs.writeFileSync(this.file, '', { encoding: 'utf8' })
    } catch {
      /* 目录不可写时静默降级为内存空态 */
    }
  }

  append(rec: Omit<MemoryRecord, 'ts'>): void {
    if (!rec.content || rec.content.length > 16_000) return
    const line = JSON.stringify({ ...rec, ts: Date.now() }) + '\n'
    try {
      fs.appendFileSync(this.file, line, { encoding: 'utf8' })
      // 滚动裁剪
      const stat = fs.statSync(this.file)
      if (stat.size > 8 * 1024 * 1024) this.trim()
    } catch {
      /* 忽略写失败（只读/磁盘满降级） */
    }
  }

  private trim(): void {
    try {
      const lines = fs.readFileSync(this.file, 'utf8').split('\n').filter(Boolean)
      const keep = lines.slice(-MAX_ROWS)
      fs.writeFileSync(this.file, keep.join('\n') + (keep.length ? '\n' : ''), { encoding: 'utf8' })
    } catch {
      /* 忽略 */
    }
  }

  query(username: string, keyword: string, limit = 50): MemorySearchResult {
    const kw = (keyword || '').toLowerCase().trim()
    if (!kw) return { records: [], total: 0 }
    try {
      const lines = fs.readFileSync(this.file, 'utf8').split('\n').filter(Boolean)
      const out: MemoryRecord[] = []
      for (let i = lines.length - 1; i >= 0 && out.length < limit; i--) {
        try {
          const rec = JSON.parse(lines[i]) as MemoryRecord
          if (rec.username === username && rec.content.toLowerCase().includes(kw)) {
            out.push(rec)
          }
        } catch {
          /* 跳过损坏行 */
        }
      }
      return { records: out, total: out.length }
    } catch {
      return { records: [], total: 0 }
    }
  }

  recent(username: string, limit = 30): MemoryRecord[] {
    try {
      const lines = fs.readFileSync(this.file, 'utf8').split('\n').filter(Boolean)
      const out: MemoryRecord[] = []
      for (let i = lines.length - 1; i >= 0 && out.length < limit; i--) {
        try {
          const rec = JSON.parse(lines[i]) as MemoryRecord
          if (rec.username === username) out.push(rec)
        } catch {
          /* skip */
        }
      }
      return out
    } catch {
      return []
    }
  }
}
