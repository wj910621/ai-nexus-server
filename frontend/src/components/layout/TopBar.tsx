import { Avatar, Dropdown, Space, Typography } from 'antd'
import { UserOutlined, LogoutOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import RealtimeStatus from '@/components/common/RealtimeStatus'
import NotificationBell from '@/components/common/NotificationBell'
import ThemeToggle from '@/components/common/ThemeToggle'

export default function TopBar() {
  const navigate = useNavigate()
  const { user, logout } = useAuthStore()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <header className="h-14 bg-[#1e1e2e] border-b border-[#313244] flex items-center justify-between px-6">
      <Typography.Title level={5} className="!text-white !mb-0">
        Y·NEX Story Studio
      </Typography.Title>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <RealtimeStatus />
        <NotificationBell />
        <ThemeToggle />
        <Dropdown
          menu={{
            items: [
              {
                key: 'logout',
                icon: <LogoutOutlined />,
                label: '退出登录',
                onClick: handleLogout,
              },
            ],
          }}
          placement="bottomRight"
        >
          <Space className="cursor-pointer">
            <Avatar icon={<UserOutlined />} src={user?.avatar_url || undefined} />
            <span className="text-white">{user?.username}</span>
          </Space>
        </Dropdown>
      </div>
    </header>
  )
}
