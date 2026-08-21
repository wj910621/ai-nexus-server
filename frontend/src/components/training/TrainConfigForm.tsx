/**
 * P3: 训练参数配置表单
 *
 * 触发词 + 预设档位选择 + 训练位置选择 + 高级参数折叠。
 */
import { Card, Radio, Space, Typography, Collapse, InputNumber, Form, Alert, Tag, Input } from 'antd'
import type { TrainPreset, TrainLocation, TrainParamsAdvanced } from '@/types/training'

const { Title, Text } = Typography

interface TrainConfigFormProps {
  triggerWord: string
  setTriggerWord: (v: string) => void
  preset: TrainPreset
  setPreset: (v: TrainPreset) => void
  location: TrainLocation
  setLocation: (v: TrainLocation) => void
  advanced: TrainParamsAdvanced
  setAdvanced: (v: TrainParamsAdvanced) => void
  gpuInfo: { vram_gb: number; device_name: string } | null
}

const PRESET_INFO: Record<TrainPreset, { steps: number; time: string; desc: string }> = {
  quick: { steps: 500, time: '~15分钟', desc: '适合测试' },
  standard: { steps: 1000, time: '~30分钟', desc: '推荐' },
  high_quality: { steps: 2000, time: '~60分钟', desc: '最终成品' },
}

const PRESET_LABEL: Record<TrainPreset, string> = {
  quick: '快速',
  standard: '标准',
  high_quality: '高质量',
}

export default function TrainConfigForm({
  triggerWord,
  setTriggerWord,
  preset,
  setPreset,
  location,
  setLocation,
  advanced,
  setAdvanced,
  gpuInfo,
}: TrainConfigFormProps) {
  const localDisabled = !gpuInfo || gpuInfo.vram_gb < 8

  return (
    <div className="train-config-form">
      <Title level={5}>触发词</Title>
      <Input
        value={triggerWord}
        onChange={(e) => setTriggerWord(e.target.value)}
        placeholder="输入触发词（如：sks girl）"
        style={{ maxWidth: 320, marginBottom: 24 }}
      />

      <Title level={5}>预设档位</Title>
      <Radio.Group
        value={preset}
        onChange={(e) => setPreset(e.target.value)}
        style={{ marginBottom: 24 }}
      >
        <Space direction="vertical">
          {(Object.keys(PRESET_INFO) as TrainPreset[]).map((key) => (
            <Radio key={key} value={key}>
              <Space>
                <Text strong>{PRESET_LABEL[key]}</Text>
                <Tag>{PRESET_INFO[key].steps} 步</Tag>
                <Text type="secondary">{PRESET_INFO[key].time}</Text>
                <Text type="secondary">{PRESET_INFO[key].desc}</Text>
              </Space>
            </Radio>
          ))}
        </Space>
      </Radio.Group>

      <Title level={5}>训练位置</Title>
      <Radio.Group
        value={location}
        onChange={(e) => setLocation(e.target.value)}
        style={{ marginBottom: 16 }}
      >
        <Space direction="vertical">
          <Radio value="local" disabled={localDisabled}>
            <Space>
              <Text>本地训练</Text>
              {gpuInfo && (
                <Tag color={gpuInfo.vram_gb >= 8 ? 'green' : 'red'}>
                  {gpuInfo.device_name} ({gpuInfo.vram_gb}GB)
                </Tag>
              )}
            </Space>
          </Radio>
          <Radio value="replicate">
            <Text>云端训练（Replicate）</Text>
          </Radio>
        </Space>
      </Radio.Group>

      {localDisabled && location === 'local' && (
        <Alert
          type="warning"
          message="本地 GPU VRAM 不足 8GB，无法本地训练"
          description="请选择云端训练或升级 GPU"
          style={{ marginBottom: 16 }}
        />
      )}

      <Collapse
        items={[
          {
            key: 'advanced',
            label: '高级参数',
            children: (
              <Form layout="inline">
                <Form.Item label="LoRA Rank">
                  <InputNumber
                    value={advanced.rank}
                    min={1}
                    max={128}
                    onChange={(v) => setAdvanced({ ...advanced, rank: v || 32 })}
                  />
                </Form.Item>
                <Form.Item label="学习率">
                  <InputNumber
                    value={advanced.learning_rate}
                    min={0.00001}
                    max={0.01}
                    step={0.0001}
                    onChange={(v) =>
                      setAdvanced({ ...advanced, learning_rate: v || 1e-4 })
                    }
                  />
                </Form.Item>
                <Form.Item label="最大步数">
                  <InputNumber
                    value={advanced.max_train_steps}
                    min={10}
                    max={10000}
                    onChange={(v) =>
                      setAdvanced({ ...advanced, max_train_steps: v || 1000 })
                    }
                  />
                </Form.Item>
              </Form>
            ),
          },
        ]}
      />

      <Card size="small" style={{ marginTop: 16 }}>
        <Text type="secondary">
          当前选择：{PRESET_LABEL[preset]} · {location === 'local' ? '本地' : '云端'} ·
          rank={advanced.rank} · lr={advanced.learning_rate}
        </Text>
      </Card>
    </div>
  )
}
