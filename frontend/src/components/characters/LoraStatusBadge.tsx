/**
 * P3: LoRA 训练状态徽章
 *
 * 在角色卡片上显示 LoRA 训练状态。
 */
import { Tag } from 'antd'

const STATUS_CONFIG: Record<string, { color: string; text: string }> = {
  none: { color: 'default', text: '未训练' },
  drafting: { color: 'blue', text: '准备中' },
  training: { color: 'processing', text: '训练中' },
  ready: { color: 'success', text: '已训练' },
  failed: { color: 'error', text: '训练失败' },
}

export default function LoraStatusBadge({ status }: { status: string }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.none
  return <Tag color={config.color}>{config.text}</Tag>
}
