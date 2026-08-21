/**
 * P3: LoRA 训练页面
 *
 * 分步向导：数据集 → Caption → 参数 → 进度
 */
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Card, Steps, Button, Space, Typography, message } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import DatasetUploader from '@/components/training/DatasetUploader'
import CaptionEditor from '@/components/training/CaptionEditor'
import TrainConfigForm from '@/components/training/TrainConfigForm'
import TrainProgressPanel from '@/components/training/TrainProgressPanel'
import {
  createDataset,
  getTrainStatus,
  submitTrain,
  deleteImage as deleteImageApi,
} from '@/api/training'
import { fetchRuntimeInfo } from '@/api/models'
import type { Dataset, DatasetItem } from '@/types/dataset'
import type { TrainPreset, TrainLocation, TrainParamsAdvanced } from '@/types/training'
import { commercialOperationsEnabled, commercialOperationsUnavailableMessage } from '@/config/commercialOperations'

const { Title } = Typography

export default function TrainingPage() {
  const { id: characterId } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [currentStep, setCurrentStep] = useState(0)
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [triggerWord, setTriggerWord] = useState('')
  const [preset, setPreset] = useState<TrainPreset>('standard')
  const [location, setLocation] = useState<TrainLocation>('local')
  const [advanced, setAdvanced] = useState<TrainParamsAdvanced>({
    rank: 32,
    learning_rate: 1e-4,
    max_train_steps: 1000,
  })
  const [gpuInfo, setGpuInfo] = useState<{ vram_gb: number; device_name: string } | null>(null)
  const [taskId, setTaskId] = useState<string | null>(null)

  // 加载 GPU 信息
  useEffect(() => {
    fetchRuntimeInfo()
      .then((resp) => {
        if (resp.data) {
          setGpuInfo({
            vram_gb: resp.data.vram_gb,
            device_name: resp.data.gpu_name,
          })
        }
      })
      .catch(() => {})
  }, [])

  // 初始化数据集
  useEffect(() => {
    if (!characterId) return
    createDataset({
      character_id: characterId,
      name: `训练数据集 ${new Date().toLocaleDateString()}`,
      caption_mode: 'auto',
      trigger_word: '',
    })
      .then((resp) => {
        if (resp.data.code === 0) {
          setDataset(resp.data.data)
        }
      })
      .catch((e) => message.error(`创建数据集失败：${e.message}`))
  }, [characterId])

  const handleItemAdded = (item: DatasetItem) => {
    if (dataset) {
      setDataset({
        ...dataset,
        items: [...dataset.items, item],
        image_count: dataset.image_count + 1,
      })
    }
  }

  const handleItemRemoved = async (itemId: string) => {
    if (!dataset) return
    try {
      await deleteImageApi(dataset.id, itemId)
      setDataset({
        ...dataset,
        items: dataset.items.filter((i) => i.id !== itemId),
        image_count: dataset.image_count - 1,
      })
    } catch (e) {
      message.error(`删除失败：${(e as Error).message}`)
    }
  }

  const handleStartTrain = async () => {
    if (!dataset || !characterId) return
    if (!triggerWord || triggerWord.length < 2) {
      message.error('请输入触发词（至少 2 个字符）')
      return
    }
    if (dataset.image_count < 5) {
      message.error('数据集至少需要 5 张图片')
      return
    }
    try {
      const resp = await submitTrain(characterId, {
        dataset_id: dataset.id,
        trigger_word: triggerWord,
        preset,
        location,
        advanced,
      })
      if (resp.data.code === 0) {
        setTaskId(resp.data.data.task_id)
        setCurrentStep(3)
        message.success('训练任务已提交')
      } else {
        message.error(resp.data.message || '提交失败')
      }
    } catch (e) {
      message.error(`提交训练失败：${(e as Error).message}`)
    }
  }

  // 轮询训练状态（WebSocket 失败时的兜底）
  useEffect(() => {
    if (!taskId || !characterId) return
    const timer = setInterval(async () => {
      try {
        const resp = await getTrainStatus(characterId)
        if (resp.data.code === 0 && resp.data.data.status === 'succeeded') {
          clearInterval(timer)
          message.success('训练完成！LoRA adapter 已生成')
        } else if (resp.data.code === 0 && resp.data.data.status === 'failed') {
          clearInterval(timer)
          message.error('训练失败，请查看日志')
        }
      } catch {
        // 忽略瞬时错误
      }
    }, 5000)
    return () => clearInterval(timer)
  }, [taskId, characterId])

  const steps = [
    {
      title: '数据集',
      content: (
        <DatasetUploader
          dataset={dataset}
          onItemAdded={handleItemAdded}
          onItemRemoved={handleItemRemoved}
        />
      ),
    },
    {
      title: 'Caption',
      content: <CaptionEditor dataset={dataset} triggerWord={triggerWord} />,
    },
    {
      title: '参数',
      content: (
        <>
          <TrainConfigForm
            triggerWord={triggerWord}
            setTriggerWord={setTriggerWord}
            preset={preset}
            setPreset={setPreset}
            location={location}
            setLocation={setLocation}
            advanced={advanced}
            setAdvanced={setAdvanced}
            gpuInfo={gpuInfo}
          />
          <Button
            type="primary"
            onClick={handleStartTrain}
            disabled={!commercialOperationsEnabled || !dataset || dataset.image_count < 5}
            title={!commercialOperationsEnabled ? commercialOperationsUnavailableMessage : undefined}
            style={{ marginTop: 16 }}
          >
            开始训练
          </Button>
        </>
      ),
    },
    {
      title: '进度',
      content: (
        <TrainProgressPanel
          taskId={taskId}
          characterId={characterId}
          onRetry={() => setCurrentStep(2)}
          onGoToGenerate={() => navigate('/image-gen')}
        />
      ),
    },
  ]

  return (
    <div className="p-6">
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
          返回
        </Button>
        <Title level={4} style={{ margin: 0 }}>
          LoRA 训练
        </Title>
      </Space>

      <Card>
        <Steps
          current={currentStep}
          items={steps.map((s) => ({ title: s.title }))}
        />
        <div style={{ marginTop: 24, minHeight: 300 }}>{steps[currentStep].content}</div>
        <div style={{ marginTop: 24, textAlign: 'right' }}>
          {currentStep > 0 && currentStep < 3 && (
            <Button
              style={{ marginRight: 8 }}
              onClick={() => setCurrentStep(currentStep - 1)}
            >
              上一步
            </Button>
          )}
          {currentStep < 2 && (
            <Button type="primary" onClick={() => setCurrentStep(currentStep + 1)}>
              下一步
            </Button>
          )}
        </div>
      </Card>
    </div>
  )
}
