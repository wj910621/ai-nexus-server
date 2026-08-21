import { useEffect, useState } from 'react'
import { Card, Progress, Empty } from 'antd'
import { Video, Image, FileText, Mic, CheckCircle } from 'lucide-react'
import { apiClient } from '@/api/client'
import { useTaskProgress } from '@/hooks/useTaskProgress'

interface Task {
  id: string
  type: 'video' | 'image' | 'tts' | 'export'
  title: string
  status: 'pending' | 'running' | 'completed' | 'failed'
}

const ICON_MAP = {
  video: Video,
  image: Image,
  tts: Mic,
  export: FileText,
}

function TaskItem({ task }: { task: Task }) {
  const progress = useTaskProgress(task.status === 'running' ? task.id : null)
  const Icon = ICON_MAP[task.type]

  if (task.status === 'completed') {
    return (
      <div style={{ marginBottom: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
          <span><Icon size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />{task.title}</span>
          <span style={{ color: 'var(--accent-emerald)' }}><CheckCircle size={14} /> 完成</span>
        </div>
      </div>
    )
  }

  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
        <span><Icon size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />{task.title}</span>
        <span style={{ color: 'var(--brand-primary)' }}>{Math.round((progress?.progress ?? 0) * 100)}%</span>
      </div>
      <Progress
        percent={Math.round((progress?.progress ?? 0) * 100)}
        size="small"
        strokeColor={{ from: '#3B82F6', to: '#6366F1' }}
      />
      {progress?.eta && (
        <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2 }}>
          预计 {progress.eta}s
        </div>
      )}
    </div>
  )
}

export default function TaskProgressList() {
  const [tasks, setTasks] = useState<Task[]>([])

  useEffect(() => {
    apiClient.get('/api/v1/tasks?status=running')
      .then((resp) => setTasks(resp.data?.items ?? []))
      .catch(() => setTasks([]))
  }, [])

  return (
    <Card title="后台任务" size="small">
      {tasks.length === 0 ? (
        <Empty description="暂无运行中任务" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        tasks.map((task) => <TaskItem key={task.id} task={task} />)
      )}
    </Card>
  )
}
