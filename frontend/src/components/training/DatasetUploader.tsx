/**
 * P3: 数据集上传组件
 *
 * 拖拽上传 5-20 张角色图片。
 */
import { useState } from 'react'
import { Upload, Button, message, Row, Col, Image, Space, Typography } from 'antd'
import { InboxOutlined, DeleteOutlined } from '@ant-design/icons'
import { uploadImage } from '@/api/training'
import type { Dataset, DatasetItem } from '@/types/dataset'

const { Dragger } = Upload
const { Text } = Typography

interface DatasetUploaderProps {
  dataset: Dataset | null
  onItemAdded: (item: DatasetItem) => void
  onItemRemoved: (itemId: string) => void
}

const MIN_IMAGES = 5
const MAX_IMAGES = 20

export default function DatasetUploader({
  dataset,
  onItemAdded,
  onItemRemoved,
}: DatasetUploaderProps) {
  const [uploading, setUploading] = useState(false)
  const items = dataset?.items ?? []

  const handleUpload = async (file: File) => {
    if (!dataset) {
      message.error('数据集尚未创建')
      return false
    }
    if (items.length >= MAX_IMAGES) {
      message.warning(`最多上传 ${MAX_IMAGES} 张图片`)
      return false
    }
    setUploading(true)
    try {
      const resp = await uploadImage(dataset.id, file)
      if (resp.data.code === 0) {
        onItemAdded(resp.data.data)
        message.success('上传成功')
      } else {
        message.error(resp.data.message || '上传失败')
      }
    } catch (e) {
      message.error(`上传失败：${(e as Error).message}`)
    } finally {
      setUploading(false)
    }
    return false // 阻止 antd 自动上传
  }

  return (
    <div className="dataset-uploader">
      <Dragger
        accept="image/png,image/jpeg"
        multiple
        showUploadList={false}
        beforeUpload={handleUpload}
        disabled={uploading || items.length >= MAX_IMAGES || !dataset}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">拖拽上传角色图片</p>
        <p className="ant-upload-hint">
          支持 JPG/PNG 格式，单张 ≤10MB，需 {MIN_IMAGES}-{MAX_IMAGES} 张
        </p>
      </Dragger>

      <div style={{ marginTop: 16 }}>
        <Space>
          <Text type={items.length < MIN_IMAGES ? 'danger' : 'secondary'}>
            已上传 {items.length}/{MAX_IMAGES} 张
            {items.length < MIN_IMAGES && `（最少 ${MIN_IMAGES} 张）`}
          </Text>
        </Space>
      </div>

      {items.length > 0 && (
        <Row gutter={[8, 8]} style={{ marginTop: 16 }}>
          {items.map((item) => (
            <Col key={item.id} span={6}>
              <div style={{ position: 'relative' }}>
                <Image
                  src={item.image_path}
                  width="100%"
                  height={120}
                  style={{ objectFit: 'cover' }}
                />
                <Button
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  style={{ position: 'absolute', top: 4, right: 4 }}
                  onClick={() => onItemRemoved(item.id)}
                />
              </div>
            </Col>
          ))}
        </Row>
      )}
    </div>
  )
}
