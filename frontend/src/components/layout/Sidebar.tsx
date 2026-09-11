import { useLocation, useNavigate } from 'react-router-dom'
import { CreditCardOutlined, DashboardOutlined, ProjectOutlined, SettingOutlined, TeamOutlined, RobotOutlined, AppstoreOutlined, ApartmentOutlined } from '@ant-design/icons'
import { Tooltip } from 'antd'

const navItems = [
  { path: '/dashboard', icon: <DashboardOutlined />, label: '仪表盘' },
  { path: '/agent', icon: <RobotOutlined />, label: '创作智能' },
  { path: '/templates', icon: <AppstoreOutlined />, label: '漫剧模板' },
  { path: '/workflow', icon: <ApartmentOutlined />, label: '节点工作流' },
  { path: '/projects', icon: <ProjectOutlined />, label: '项目' },
  { path: '/characters', icon: <TeamOutlined />, label: '角色库' },
  { path: '/billing', icon: <CreditCardOutlined />, label: '套餐与账单' },
  { path: '/settings', icon: <SettingOutlined />, label: '设置' },
]

export default function Sidebar() {
  const navigate = useNavigate()
  const location = useLocation()
  return <aside className="w-16 bg-[#11111b] flex flex-col items-center py-4 gap-2 border-r border-[#313244]">
    <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-bold mb-4" aria-label="Y·NEX">Y</div>
    {navItems.map((item) => {
      const active = location.pathname.startsWith(item.path)
      return <Tooltip key={item.path} title={item.label} placement="right"><button aria-label={item.label} onClick={() => navigate(item.path)} className={`w-10 h-10 rounded-lg flex items-center justify-center text-lg transition-colors ${active ? 'bg-[#3b3f54] text-white' : 'text-gray-400 hover:bg-[#2a2a3e] hover:text-white'}`}>{item.icon}</button></Tooltip>
    })}
  </aside>
}
