import { useState } from 'react'
import { Card, Row, Col, Button, Modal, Form, Input, Select, Empty, Spin, message } from 'antd'
import { PlusOutlined, ProjectOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useProjects, useCreateProject } from '@/hooks/useProjects'

export default function ProjectListPage() {
  const navigate = useNavigate()
  const { data, isLoading } = useProjects()
  const createMutation = useCreateProject()
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()

  const handleCreate = async () => {
    try {
      const values = await form.validateFields()
      const project = await createMutation.mutateAsync(values)
      message.success('创建成功')
      setModalOpen(false)
      form.resetFields()
      navigate(`/projects/${project.id}`)
    } catch {
      // 校验错误已处理
    }
  }

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-white text-xl">我的项目</h2>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          新建项目
        </Button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-20">
          <Spin size="large" />
        </div>
      ) : !data?.items?.length ? (
        <Empty
          description={<span className="text-gray-400">暂无项目，点击右上角创建</span>}
          className="py-20"
        />
      ) : (
        <Row gutter={[16, 16]}>
          {data.items.map((p) => (
            <Col xs={24} sm={12} md={8} lg={6} key={p.id}>
              <Card
                hoverable
                className="!bg-[#1e1e2e] !border-[#313244]"
                onClick={() => navigate(`/projects/${p.id}`)}
              >
                <div className="flex items-center gap-3">
                  <ProjectOutlined className="text-blue-400 text-2xl" />
                  <div className="flex-1 min-w-0">
                    <div className="text-white font-medium truncate">{p.name}</div>
                    <div className="text-gray-400 text-xs truncate">
                      {p.description || '暂无描述'}
                    </div>
                  </div>
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Modal
        title="新建项目"
        open={modalOpen}
        onOk={handleCreate}
        onCancel={() => setModalOpen(false)}
        confirmLoading={createMutation.isPending}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="项目名称" rules={[{ required: true }]}>
            <Input placeholder="输入项目名称" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea placeholder="项目描述" rows={3} />
          </Form.Item>
          <Form.Item name="genre" label="类型">
            <Select
              placeholder="选择类型"
              options={[
                { value: 'romance', label: '言情' },
                { value: 'action', label: '动作' },
                { value: 'mystery', label: '悬疑' },
                { value: 'comedy', label: '喜剧' },
                { value: 'drama', label: '剧情' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
