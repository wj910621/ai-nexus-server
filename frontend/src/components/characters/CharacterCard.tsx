/**
 * CharacterCard: 角色卡片组件
 *
 * 展示角色基本信息，并在卡片底部显示 LoRA 训练状态徽章和操作按钮：
 * - none / failed: 显示"训练 LoRA"按钮（跳转训练页）
 * - training: 徽章可点击跳转训练页，附带"查看进度"按钮
 * - ready: 显示"用此角色生图"按钮
 */
import { Link } from 'react-router-dom'
import { Card, Button, Space } from 'antd'
import LoraStatusBadge from './LoraStatusBadge'
import type { Character } from '@/types/character'
import { commercialOperationsEnabled, commercialOperationsUnavailableMessage } from '@/config/commercialOperations'

interface CharacterCardProps {
  character: Character
}

export default function CharacterCard({ character }: CharacterCardProps) {
  const status = character.lora_training_status || 'none'
  const trainLink = `/characters/${character.id}/train`

  const badge = <LoraStatusBadge status={status} />

  return (
    <Card title={character.name} style={{ width: 280 }}>
      {character.description && <p>{character.description}</p>}
      <Space style={{ marginTop: 8 }}>
        {status === 'training' ? <Link to={trainLink}>{badge}</Link> : badge}
        {(status === 'none' || status === 'failed') && (
          <Link to={trainLink}>
            <Button size="small" type="primary">
              训练 LoRA
            </Button>
          </Link>
        )}
        {status === 'training' && (
          <Link to={trainLink}>
            <Button size="small">查看进度</Button>
          </Link>
        )}
        {status === 'ready' && commercialOperationsEnabled && (
          <Link to={`/image-gen?character=${character.id}`}>
            <Button size="small" type="primary">
              用此角色生图
            </Button>
          </Link>
        )}
        {status === 'ready' && !commercialOperationsEnabled && (
          <Button size="small" disabled title={commercialOperationsUnavailableMessage}>用此角色生图（暂未开放）</Button>
        )}
      </Space>
    </Card>
  )
}
