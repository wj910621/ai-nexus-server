/**
 * P3: Caption 编辑组件
 *
 * 支持自动生成和手动编辑两种模式。
 */
import { useState } from 'react'
import { Button, Input, Radio, Row, Col, Image, message, Spin } from 'antd'
import { ThunderboltOutlined } from '@ant-design/icons'
import { autoCaption, updateCaption } from '@/api/training'
import type { Dataset, DatasetItem } from '@/types/dataset'
import { commercialOperationsEnabled, commercialOperationsUnavailableMessage } from '@/config/commercialOperations'

interface CaptionEditorProps {
  dataset: Dataset | null
  triggerWord: string
  onCaptionUpdated?: (item: DatasetItem) => void
}

export default function CaptionEditor({
  dataset,
  triggerWord,
  onCaptionUpdated,
}: CaptionEditorProps) {
  const [mode, setMode] = useState<'auto' | 'manual'>('auto')
  const [generating, setGenerating] = useState(false)
  const items = dataset?.items ?? []

  const handleAutoGenerate = async () => {
    if (!commercialOperationsEnabled) {
      message.warning(commercialOperationsUnavailableMessage)
      return
    }
    if (!dataset) {
      message.error('数据集尚未创建')
      return
    }
    setGenerating(true)
    try {
      const resp = await autoCaption(dataset.id)
      if (resp.data.code === 0) {
        message.success(`已生成 ${resp.data.data.count} 条 caption`)
        // 重新加载 items 由父组件处理
      } else {
        message.error(resp.data.message || '生成失败')
      }
    } catch (e) {
      message.error(`生成失败：${(e as Error).message}`)
    } finally {
      setGenerating(false)
    }
  }

  const handleManualEdit = async (item: DatasetItem, caption: string) => {
    if (!dataset) return
    try {
      const resp = await updateCaption(dataset.id, item.id, caption)
      if (resp.data.code === 0) {
        onCaptionUpdated?.(resp.data.data)
      }
    } catch (e) {
      message.error(`保存失败：${(e as Error).message}`)
    }
  }

  return (
    <div className="caption-editor">
      <Row style={{ marginBottom: 16 }}>
        <Radio.Group value={mode} onChange={(e) => setMode(e.target.value)}>
          <Radio.Button value="auto">
            <ThunderboltOutlined /> 自动生成
          </Radio.Button>
          <Radio.Button value="manual">手动编辑</Radio.Button>
        </Radio.Group>
      </Row>

      {mode === 'auto' && (
        <div style={{ marginBottom: 16 }}>
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            loading={generating}
            onClick={handleAutoGenerate}
            disabled={!commercialOperationsEnabled || items.length === 0 || !dataset}
            title={!commercialOperationsEnabled ? commercialOperationsUnavailableMessage : undefined}
          >
            生成 Caption
          </Button>
          {triggerWord && (
            <span style={{ marginLeft: 12, color: 'var(--text-secondary)' }}>
              触发词: <strong>{triggerWord}</strong>
            </span>
          )}
        </div>
      )}

      <Spin spinning={generating}>
        <Row gutter={[8, 16]}>
          {items.map((item) => (
            <Col key={item.id} span={24}>
              <Row gutter={16}>
                <Col span={6}>
                  <Image
                    src={item.image_path}
                    width="100%"
                    height={100}
                    style={{ objectFit: 'cover' }}
                  />
                </Col>
                <Col span={18}>
                  <Input.TextArea
                    value={item.caption}
                    onChange={(e) => handleManualEdit(item, e.target.value)}
                    placeholder="输入图片描述..."
                    autoSize={{ minRows: 3, maxRows: 5 }}
                    disabled={mode === 'auto' && item.caption_source === 'auto'}
                  />
                </Col>
              </Row>
            </Col>
          ))}
        </Row>
      </Spin>
    </div>
  )
}
