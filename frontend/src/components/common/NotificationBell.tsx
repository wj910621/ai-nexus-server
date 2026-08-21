import { useState } from 'react'
import { Badge, Dropdown, Button, List, Typography } from 'antd'
import { Bell } from 'lucide-react'
import { useNotifications } from '@/hooks/useNotifications'
import { useRealtimeStore } from '@/stores/realtimeStore'

const { Text } = Typography

export default function NotificationBell() {
  const notifications = useNotifications()
  const markAllRead = useRealtimeStore((s) => s.markAllRead)
  const unreadCount = notifications.filter((n) => !n.read).length
  const [open, setOpen] = useState(false)

  const icon = (
    <Badge count={unreadCount} size="small" offset={[-2, 2]}>
      <Bell size={18} />
    </Badge>
  )

  const dropdownContent = (
    <div style={{ width: 320, background: 'var(--bg-elevated)', borderRadius: 8, boxShadow: 'var(--shadow-lg)' }}>
      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-default)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text strong>通知 ({unreadCount} 未读)</Text>
        <Button type="link" size="small" onClick={markAllRead}>全部已读</Button>
      </div>
      <List
        size="small"
        dataSource={notifications.slice(-10).reverse()}
        renderItem={(n) => (
          <List.Item style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-subtle)', background: n.read ? 'transparent' : 'rgba(59, 130, 246, 0.06)' }}>
            <List.Item.Meta
              title={<Text strong style={{ fontSize: 13 }}>{n.title}</Text>}
              description={<Text type="secondary" style={{ fontSize: 12 }}>{n.body}</Text>}
            />
          </List.Item>
        )}
        locale={{ emptyText: '暂无通知' }}
      />
    </div>
  )

  return (
    <Dropdown
      overlay={dropdownContent}
      trigger={['click']}
      placement="bottomRight"
      open={open}
      onOpenChange={setOpen}
    >
      {icon}
    </Dropdown>
  )
}
