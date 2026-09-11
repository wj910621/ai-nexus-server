import { Card, Col, Row, Statistic, Typography } from 'antd'
import { ProjectOutlined, RobotOutlined, AppstoreOutlined, VideoCameraOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { useAssetStore } from '@/stores/assetStore'
import { useJobStore } from '@/stores/jobStore'
import TaskProgressList from '@/components/dashboard/TaskProgressList'

export default function DashboardPage() {
  const { user } = useAuthStore()
  const navigate = useNavigate()
  const assetCount = useAssetStore((s) => s.assets.length)
  const jobCount = useJobStore((s) => s.jobs.length)

  const stats = [
    { title: '项目数', value: 0, icon: <ProjectOutlined />, color: '#3b82f6' },
    { title: '脚本资产', value: assetCount, icon: <RobotOutlined />, color: '#8b5cf6' },
    { title: '出片任务', value: jobCount, icon: <VideoCameraOutlined />, color: '#f59e0b' },
    { title: '云端项目', value: 0, icon: <AppstoreOutlined />, color: '#10b981' },
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
          <Col xs={24} sm={8}>
            <Card
              hoverable
              className="!bg-[#2a2a3e] !border-[#313244] text-center"
              onClick={() => navigate('/projects')}
            >
              <ProjectOutlined style={{ fontSize: 32, color: '#3b82f6' }} />
              <Typography.Text className="!text-white block mt-2">新建项目</Typography.Text>
            </Card>
          </Col>
          <Col xs={24} sm={8}>
            <Card
              hoverable
              className="!bg-[#2a2a3e] !border-[#313244] text-center"
              onClick={() => navigate('/agent')}
            >
              <RobotOutlined style={{ fontSize: 32, color: '#8b5cf6' }} />
              <Typography.Text className="!text-white block mt-2">创作智能 Agent</Typography.Text>
            </Card>
          </Col>
          <Col xs={24} sm={8}>
            <Card
              hoverable
              className="!bg-[#2a2a3e] !border-[#313244] text-center"
              onClick={() => navigate('/templates')}
            >
              <AppstoreOutlined style={{ fontSize: 32, color: '#10b981' }} />
              <Typography.Text className="!text-white block mt-2">漫剧模板 · 一键出片</Typography.Text>
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
