/**
 * P3: 训练进度面板
 *
 * 通过 useTaskProgress 订阅 WebSocket 频道 task:{task_id}，
 * 实时展示训练进度。失败时支持重试，完成后支持下载与跳转生图。
 */
import { useEffect, useState } from 'react'
import { Progress, Card, Typography, Button, Space, Alert } from 'antd'
import { CheckCircleOutlined, ReloadOutlined, DownloadOutlined } from '@ant-design/icons'
import { useTaskProgress } from '@/hooks/useTaskProgress'
import { commercialOperationsEnabled, commercialOperationsUnavailableMessage } from '@/config/commercialOperations'

const { Title, Text } = Typography

interface TrainProgressPanelProps {
  taskId: string | null
  characterId?: string
  onRetry?: () => void
  onGoToGenerate?: () => void
}

type PanelStatus = 'pending' | 'training' | 'done' | 'failed'

export default function TrainProgressPanel({
  taskId,
  characterId,
  onRetry,
  onGoToGenerate,
}: TrainProgressPanelProps) {
  const progress = useTaskProgress(taskId)
  const [status, setStatus] = useState<PanelStatus>('pending')

  useEffect(() => {
    if (!progress) return
    if (progress.status === 'completed') setStatus('done')
    else if (progress.status === 'failed' || progress.status === 'cancelled') setStatus('failed')
    else if (progress.status === 'running') setStatus('training')
    else if (progress.status === 'pending') setStatus('pending')
  }, [progress])

  if (!taskId) {
    return (
      <Card>
        <Text type="secondary">等待提交训练任务...</Text>
      </Card>
    )
  }

  const percent = progress ? Math.round(progress.progress * 100) : 0

  return (
    <Card>
      {status === 'done' ? (
        <>
          <Alert
            type="success"
            message="训练完成！"
            description="LoRA adapter 已保存，该角色后续生图将自动使用。"
            showIcon
            icon={<CheckCircleOutlined />}
            style={{ marginBottom: 16 }}
          />
          <Space>
            {characterId && (
              <Button
                type="primary"
                icon={<DownloadOutlined />}
                href={`/api/v1/characters/${characterId}/lora`}
              >
                下载 LoRA
              </Button>
            )}
            {onGoToGenerate && (
              <Button
                onClick={onGoToGenerate}
                disabled={!commercialOperationsEnabled}
                title={!commercialOperationsEnabled ? commercialOperationsUnavailableMessage : undefined}
              >
                {commercialOperationsEnabled ? '用此角色生图' : '用此角色生图（暂未开放）'}
              </Button>
            )}
          </Space>
        </>
      ) : status === 'failed' ? (
        <>
          <Alert
            type="error"
            message="训练失败"
            description={progress?.stage || progress?.error || '未知错误'}
            style={{ marginBottom: 16 }}
          />
          {onRetry && (
            <Button icon={<ReloadOutlined />} onClick={onRetry}>
              重试
            </Button>
          )}
        </>
      ) : (
        <>
          <Title level={5}>训练进度</Title>
          <Progress percent={percent} status={status === 'training' ? 'active' : 'normal'} />
          <Text type="secondary">
            {progress?.stage || '准备中...'}
          </Text>
        </>
      )}
    </Card>
  )
}
