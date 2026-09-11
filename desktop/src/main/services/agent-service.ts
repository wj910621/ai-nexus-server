/**
 * P3 创作智能层 —— Agent 对话服务（TS 原生）
 *
 * 目标（对齐合并评审 §三.1）：漫剧出片所需"剧本/对白/风格/脚本"由 Agent 生成
 *  → 再交给执行层；即"创作智能层 = 编排主站多模型 + 结构化输出"。
 *
 * 实现：主站 OpenAI 兼容网关 /v1/chat/completions（与既有 /v1/ 同源）。
 *  token 由外部注入（P1 account 层提供），避免重复读存储。
 */
export interface AgentMessage {
  role: 'system' | 'user' | 'assistant'
  content: string
}

export interface AgentChatOptions {
  model: string
  temperature?: number
  maxTokens?: number
}

export type AgentResult =
  | { ok: true; content: string; model: string }
  | { ok: false; code: 'unauthorized' | 'network' | 'invalid' | 'quota'; message: string }

type TokenProvider = () => string | null
type HttpLike = (url: string, init?: { method?: string; headers?: Record<string, string>; body?: string; signal?: AbortSignal }) => Promise<{ ok: boolean; status: number; json(): Promise<unknown> }>

const MODEL_ALIASES: Record<string, string> = {
  'deepseek-chat': 'deepseek/deepseek-chat',
  'deepseek-v3': 'deepseek/deepseek-chat',
  'qwen-plus': 'qwen/qwen-plus',
  'qwen-flash': 'qwen/qwen-flash',
  'kimi-k2': 'moonshot/kimi-k2',
  'hunyuan-turbos': 'hunyuan/turbos',
}

export class AgentService {
  constructor(
    private readonly tokenProvider: TokenProvider,
    private readonly apiBase: string,
    private readonly http: HttpLike = (...args) => fetch(...(args as [any, any])) as unknown as ReturnType<HttpLike>,
  ) {}

  private resolveModel(model: string): string {
    return MODEL_ALIASES[model] ?? model
  }

  async chat(messages: AgentMessage[], opts: AgentChatOptions): Promise<AgentResult> {
    if (!opts.model) return { ok: false, code: 'invalid', message: '请选择模型' }
    const token = this.tokenProvider()
    if (!token) return { ok: false, code: 'unauthorized', message: '请先登录主站账号' }
    if (!messages.length || !messages.some((m) => m.content?.trim())) {
      return { ok: false, code: 'invalid', message: '消息不能为空' }
    }
    try {
      const ctrl = new AbortController()
      const timer = setTimeout(() => ctrl.abort(), 60_000)
      const res = await this.http(`${this.apiBase}/v1/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          model: this.resolveModel(opts.model),
          messages,
          temperature: opts.temperature ?? 0.7,
          max_tokens: opts.maxTokens ?? 2048,
        }),
        signal: ctrl.signal,
      })
      clearTimeout(timer)
      if (res.status === 401 || res.status === 403) return { ok: false, code: 'unauthorized', message: '登录已过期，请重新登录' }
      const body = (await res.json().catch(() => null)) as {
        choices?: Array<{ message?: { content?: string } }>
        error?: { message?: string }
      } | null
      if (!res.ok || !body) {
        const msg = (body as { error?: { message?: string } } | null)?.error?.message
        const quotaLike = /quota|balance|credits|insufficient|余额|积分/i.test(msg ?? '')
        return {
          ok: false,
          code: quotaLike ? 'quota' : 'invalid',
          message: msg || '请求失败，请稍后重试',
        }
      }
      const content = body.choices?.[0]?.message?.content
      if (!content) return { ok: false, code: 'invalid', message: '模型未返回内容' }
      return { ok: true, content, model: opts.model }
    } catch (err) {
      const aborted = err instanceof Error && err.name === 'AbortError'
      return { ok: false, code: 'network', message: aborted ? '请求超时，请重试' : '网络错误，请检查网络' }
    }
  }

  /** 结构化创作辅助：按用户模板产出（后续漫剧 job 调用方） */
  async createComicScript(premise: string, genre: string): Promise<AgentResult> {
    const prompt = [
      `你是资深漫剧编剧。请基于以下故事梗概产出可交付的漫剧分镜脚本（JSON），不要多余解释。`,
      `题材：${genre}`,
      `梗概：${premise || '（未提供，请用通用冒险题材示例）'}`,
      `输出 JSON 结构：{"title": "...", "shots": [{"shot_no":1,"scene_prompt":"画面词","dialogue":"对白","duration_s":3}...]}`,
    ].join('\n')
    return this.chat([{ role: 'user', content: prompt }], { model: 'deepseek-chat', maxTokens: 4096 })
  }
}
