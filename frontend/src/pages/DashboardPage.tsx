import { Card, Col, Row, Statistic, Typography } from 'antd'
import { ProjectOutlined, TeamOutlined, FileTextOutlined, VideoCameraOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import TaskProgressList from '@/components/dashboard/TaskProgressList'

export default function DashboardPage() {
  const { user } = useAuthStore()
  const navigate = useNavigate()

  const stats = [
    { title: '项目数', value: 0, icon: <ProjectOutlined />, color: '#3b82f6' },
    { title: '角色数', value: 0, icon: <TeamOutlined />, color: '#8b5cf6' },
    { title: '剧本数', value: 0, icon: <FileTextOutlined />, color: '#10b981' },
    { title: '渲染任务', value: 0, icon: <VideoCameraOutlined />, color: '#f59e0b' },
  ]

  return (
    <div className="p-6">
      <Typography.Title level={3} className="!text-white !mb-6">
        欢迎回来，{user?.username} 👋
      </Typography.Title>
      <Row gutter={[16, 16]}>
        {stats.map((s) => (
          <Col xs={12} sm={12} md={6} key={s.title}>
            <Card className="!bg-[#1e1e2e] !border-[#313244]">
              <Statistic
                title={<span className="!text-gray-400">{s.title}</span>}
                value={s.value}
                prefix={<span style={{ color: s.color }}>{s.icon}</span>}
                valueStyle={{ color: '#fff' }}
              />
            </Card>
          </Col>
        ))}
      </Row>

      <Card
        title={<span className="!text-white">快速开始</span>}
        className="!bg-[#1e1e2e] !border-[#313244] mt-6"
      >
        <Row gutter={[16, 16]}>
          <Col span={8}>
            <Card
              hoverable
              className="!bg-[#2a2a3e] !border-[#313244] text-center"
              onClick={() => navigate('/projects')}
            >
              <ProjectOutlined style={{ fontSize: 32, color: '#3b82f6' }} />
              <Typography.Text className="!text-white block mt-2">新建项目</Typography.Text>
            </Card>
          </Col>
          <Col span={8}>
            <Card hoverable className="!bg-[#2a2a3e] !border-[#313244] text-center">
              <TeamOutlined style={{ fontSize: 32, color: '#8b5cf6' }} />
              <Typography.Text className="!text-white block mt-2">创建角色</Typography.Text>
            </Card>
          </Col>
          <Col span={8}>
            <Card hoverable className="!bg-[#2a2a3e] !border-[#313244] text-center">
              <FileTextOutlined style={{ fontSize: 32, color: '#10b981' }} />
              <Typography.Text className="!text-white block mt-2">编写剧本</Typography.Text>
            </Card>
          </Col>
        </Row>
      </Card>

      <Row gutter={[16, 16]} className="mt-6">
        <Col xs={24} md={12}>
          <TaskProgressList />
        </Col>
      </Row>
    </div>
  )
}
