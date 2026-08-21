import { Tooltip } from 'antd'
import { useRealtimeStore } from '@/stores/realtimeStore'
import { wsClient } from '@/api/websocket'
import { tokenStorage } from '@/utils/token'

const STATUS_CONFIG = {
  connected: { color: 'var(--accent-emerald)', label: '已连接' },
  connecting: { color: 'var(--accent-amber)', label: '连接中...' },
  reconnecting: { color: 'var(--accent-amber)', label: '重连中...' },
  closed: { color: 'var(--accent-rose)', label: '连接断开' },
  idle: { color: 'var(--text-tertiary)', label: '未连接' },
}

export default function RealtimeStatus() {
  const wsStatus = useRealtimeStore((s) => s.wsStatus)
  const config = STATUS_CONFIG[wsStatus]

  return (
    <Tooltip title={`${config.label}${wsStatus === 'closed' ? '（点击重试）' : ''}`}>
      <div
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: config.color,
          cursor: wsStatus === 'closed' ? 'pointer' : 'default',
          animation: wsStatus === 'connecting' || wsStatus === 'reconnecting' ? 'pulse-dot 2s ease-in-out infinite' : 'none',
        }}
        onClick={() => {
          if (wsStatus === 'closed') {
            const token = tokenStorage.getAccessToken()
            if (token) wsClient.connect(token)
          }
        }}
      />
    </Tooltip>
  )
}
