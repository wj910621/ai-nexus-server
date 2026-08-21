import { useParams, useNavigate } from 'react-router-dom'
import { Button, Space, Typography, message } from 'antd'
import { ArrowLeftOutlined, PlayCircleOutlined, SaveOutlined } from '@ant-design/icons'
import WorkflowEditor from '@/components/workflow/WorkflowEditor'
import ChatPanel from '@/components/project/ChatPanel'
import { useEditorStore } from '@/stores/editorStore'
import {
  commercialOperationsEnabled,
  commercialOperationsUnavailableMessage,
} from '@/config/commercialOperations'

export default function ProjectEditorPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const { nodes, edges } = useEditorStore()

  const handleSave = () => {
    message.success(`已保存工作流 (${nodes.length} 节点, ${edges.length} 连线)`)
  }

  const handleRun = () => {
    if (!commercialOperationsEnabled) {
      message.warning(commercialOperationsUnavailableMessage)
      return
    }
    message.info('工作流执行功能将在 AI 引擎阶段实现')
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-2 bg-[#1e1e2e] border-b border-[#313244]">
        <Space>
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/projects')}
            className="!text-white"
          />
          <Typography.Text className="!text-white">
            项目: {projectId}
          </Typography.Text>
        </Space>
        <Space>
          <Button icon={<SaveOutlined />} onClick={handleSave} className="!text-white">
            保存
          </Button>
          <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleRun} disabled={!commercialOperationsEnabled} title={!commercialOperationsEnabled ? commercialOperationsUnavailableMessage : undefined}>
            运行
          </Button>
        </Space>
      </div>
      <div className="flex-1 flex">
        <div className="flex-1">
          <WorkflowEditor />
        </div>
        <div style={{ width: 380, borderLeft: '1px solid var(--border-default)' }}>
          <ChatPanel />
        </div>
      </div>
    </div>
  )
}
