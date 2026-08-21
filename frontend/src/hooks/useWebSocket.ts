import { useEffect, useState } from 'react'
import { wsClient, WSMessage } from '@/api/websocket'
import { tokenStorage } from '@/utils/token'

/**
 * 订阅指定 WS 频道
 * @param channel 频道名（如 'task:123'）；传 null 不订阅
 * @returns 最新消息
 */
export function useWebSocket(channel: string | null): WSMessage | null {
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null)

  useEffect(() => {
    if (!channel) return

    // 确保已认证并连接
    const token = tokenStorage.getAccessToken()
    if (token && wsClient.getStatus() === 'idle') {
      wsClient.connect(token).catch(() => {
        // 连接失败由重连机制处理
      })
    }

    const unsubscribe = wsClient.subscribe(channel, (msg) => {
      setLastMessage(msg)
    })

    return unsubscribe
  }, [channel])

  return lastMessage
}
