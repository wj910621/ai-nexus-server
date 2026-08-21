import { getWebSocketUrl } from '@/utils/runtime'

export type WSStatus = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'closed'

export interface WSMessage {
  type: 'subscribed' | 'unsubscribed' | 'pong' | 'error' | string
  channel?: string
  data?: unknown
  [key: string]: unknown
}

type ChannelHandler = (msg: WSMessage) => void

const HEARTBEAT_INTERVAL = 30000
const HEARTBEAT_TIMEOUT = 10000
const MAX_RECONNECT_ATTEMPTS = 5
const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000, 30000]

class WebSocketClient {
  private ws: WebSocket | null = null
  private status: WSStatus = 'idle'
  private token: string | null = null
  private channelRefs: Map<string, number> = new Map()
  private handlers: Map<string, Set<ChannelHandler>> = new Map()
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null
  private heartbeatTimeoutTimer: ReturnType<typeof setTimeout> | null = null
  private reconnectAttempts = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private statusListeners: Set<(s: WSStatus) => void> = new Set()

  async connect(token: string): Promise<void> {
    if (this.status === 'connected' || this.status === 'connecting') {
      if (this.token === token) return
      await this.disconnect()
    }
    this.token = token
    this.setStatus('connecting')
    return this._doConnect()
  }

  private _doConnect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!this.token) {
        reject(new Error('No token'))
        return
      }
      const url = getWebSocketUrl(this.token)
      this.ws = new WebSocket(url)

      this.ws.onopen = () => {
        this.setStatus('connected')
        this.reconnectAttempts = 0
        this._startHeartbeat()
        this._resubscribeAll()
        resolve()
      }

      this.ws.onmessage = (event) => {
        this._handleMessage(event.data)
      }

      this.ws.onclose = (event) => {
        this._cleanup()
        if (event.code === 4001) {
          // 认证失败，不重连
          this.setStatus('closed')
          this._dispatchStatusToListeners()
          return
        }
        this._scheduleReconnect()
      }

      this.ws.onerror = () => {
        // onclose 会随后触发，重连逻辑在 onclose 中处理
      }
    })
  }

  async disconnect(): Promise<void> {
    this._cleanup()
    if (this.ws) {
      this.ws.onclose = null
      this.ws.close()
      this.ws = null
    }
    this.setStatus('idle')
  }

  subscribe(channel: string, handler: ChannelHandler): () => void {
    // 引用计数
    const count = this.channelRefs.get(channel) ?? 0
    this.channelRefs.set(channel, count + 1)

    // 首次订阅发送 subscribe 消息
    if (count === 0 && this.status === 'connected') {
      this._send({ type: 'subscribe', channel })
    }

    // 注册 handler
    if (!this.handlers.has(channel)) {
      this.handlers.set(channel, new Set())
    }
    this.handlers.get(channel)!.add(handler)

    // 返回取消订阅函数
    return () => {
      const handlers = this.handlers.get(channel)
      if (handlers) {
        handlers.delete(handler)
        if (handlers.size === 0) {
          this.handlers.delete(channel)
        }
      }
      const newCount = (this.channelRefs.get(channel) ?? 1) - 1
      if (newCount <= 0) {
        this.channelRefs.delete(channel)
        if (this.status === 'connected') {
          this._send({ type: 'unsubscribe', channel })
        }
      } else {
        this.channelRefs.set(channel, newCount)
      }
    }
  }

  getStatus(): WSStatus {
    return this.status
  }

  onStatusChange(cb: (s: WSStatus) => void): () => void {
    this.statusListeners.add(cb)
    cb(this.status)
    return () => this.statusListeners.delete(cb)
  }

  async reconnectWithToken(token: string): Promise<void> {
    await this.disconnect()
    await this.connect(token)
  }

  private _send(msg: unknown): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg))
    }
  }

  private _handleMessage(raw: string): void {
    let msg: WSMessage
    try {
      msg = JSON.parse(raw)
    } catch {
      return
    }

    // 控制消息
    if (msg.type === 'pong') {
      this._clearHeartbeatTimeout()
      return
    }
    if (msg.type === 'subscribed' || msg.type === 'unsubscribed' || msg.type === 'error') {
      return
    }

    // 业务消息：按 channel 分发
    if (msg.channel) {
      const handlers = this.handlers.get(msg.channel)
      if (handlers) {
        handlers.forEach((h) => h(msg))
      }
    }
  }

  private _startHeartbeat(): void {
    this._clearHeartbeat()
    this.heartbeatTimer = setInterval(() => {
      this._send({ type: 'ping' })
      this.heartbeatTimeoutTimer = setTimeout(() => {
        // 心跳超时，强制重连
        if (this.ws) {
          this.ws.close()
        }
      }, HEARTBEAT_TIMEOUT)
    }, HEARTBEAT_INTERVAL)
  }

  private _clearHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
    this._clearHeartbeatTimeout()
  }

  private _clearHeartbeatTimeout(): void {
    if (this.heartbeatTimeoutTimer) {
      clearTimeout(this.heartbeatTimeoutTimer)
      this.heartbeatTimeoutTimer = null
    }
  }

  private _scheduleReconnect(): void {
    if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      this.setStatus('closed')
      return
    }
    const delay = RECONNECT_DELAYS[Math.min(this.reconnectAttempts, RECONNECT_DELAYS.length - 1)]
    this.setStatus('reconnecting')
    this.reconnectAttempts++
    this.reconnectTimer = setTimeout(() => {
      this._doConnect().catch(() => {
        // 连接失败，_doConnect 的 onclose 会再次调度重连
      })
    }, delay)
  }

  private _resubscribeAll(): void {
    for (const channel of this.channelRefs.keys()) {
      this._send({ type: 'subscribe', channel })
    }
  }

  private _cleanup(): void {
    this._clearHeartbeat()
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
  }

  private setStatus(s: WSStatus): void {
    this.status = s
    this._dispatchStatusToListeners()
  }

  private _dispatchStatusToListeners(): void {
    this.statusListeners.forEach((cb) => cb(this.status))
  }
}

export const wsClient = new WebSocketClient()
