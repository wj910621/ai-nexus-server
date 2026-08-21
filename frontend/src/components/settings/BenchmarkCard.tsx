/**
 * P2 Task 16: 硬件基准测试卡片
 *
 * 展示 DeviceManager 检测的设备信息和 BenchmarkSuite 测得的性能指标。
 * 提供 "运行基准测试" / "强制重测" 两个按钮。
 */
import { useState } from 'react';
import { Button, Card, Descriptions, Statistic, message, Tag, Space } from 'antd';
import {
  PlayCircleOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import { runBenchmark, type BenchmarkResult } from '@/api/benchmark';

const VENDOR_LABEL: Record<string, { label: string; color: string }> = {
  nvidia: { label: 'NVIDIA', color: 'green' },
  amd: { label: 'AMD', color: 'red' },
  intel: { label: 'Intel', color: 'blue' },
  none: { label: 'CPU', color: 'default' },
};

const METRIC_LABEL: Record<string, string> = {
  llm_tokens_per_sec: 'LLM 生成速度',
  image_seconds: '图像生成耗时',
  vram_peak_gb: 'VRAM 峰值',
};

export default function BenchmarkCard() {
  const [result, setResult] = useState<BenchmarkResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleRun(force: boolean) {
    setLoading(true);
    try {
      const resp = await runBenchmark(force);
      if (resp.success && resp.data) {
        setResult(resp.data);
        message.success('基准测试完成');
      } else {
        message.error(resp.message || '基准测试失败');
      }
    } catch (e) {
      message.error(`请求失败：${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  const vendorInfo = result?.device?.vendor
    ? VENDOR_LABEL[result.device.vendor]
    : null;

  return (
    <div className="benchmark-card">
      <Space style={{ marginBottom: 16 }}>
        <Button
          type="primary"
          icon={<PlayCircleOutlined />}
          loading={loading}
          onClick={() => handleRun(false)}
        >
          运行基准测试
        </Button>
        <Button
          icon={<ReloadOutlined />}
          loading={loading}
          onClick={() => handleRun(true)}
        >
          强制重测
        </Button>
      </Space>

      {result && (
        <>
          <Card
            size="small"
            title="设备信息"
            style={{ marginBottom: 16 }}
          >
            <Descriptions column={1} size="small">
              <Descriptions.Item label="厂商">
                {vendorInfo ? (
                  <Tag color={vendorInfo.color}>{vendorInfo.label}</Tag>
                ) : (
                  result.device.vendor
                )}
              </Descriptions.Item>
              <Descriptions.Item label="设备名称">
                {result.device.device_name}
              </Descriptions.Item>
              <Descriptions.Item label="显存 (GB)">
                {result.device.vram_gb.toFixed(2)}
              </Descriptions.Item>
              {result.device.backend && (
                <Descriptions.Item label="后端">
                  {result.device.backend}
                </Descriptions.Item>
              )}
            </Descriptions>
          </Card>

          <Card title="性能指标" size="small">
            <Space wrap>
              {result.metrics.map((m) => (
                <Card
                  key={m.name}
                  size="small"
                  style={{ width: 200, marginRight: 8, marginBottom: 8 }}
                >
                  <Statistic
                    title={METRIC_LABEL[m.name] || m.name}
                    value={m.value}
                    suffix={m.unit}
                    valueStyle={{ fontSize: 20 }}
                  />
                </Card>
              ))}
              {result.metrics.length === 0 && (
                <Tag icon={<CheckCircleOutlined />} color="default">
                  暂无指标（CPU 模式或测试未执行）
                </Tag>
              )}
            </Space>
          </Card>

          <div style={{ marginTop: 8, color: 'var(--text-secondary)', fontSize: 12 }}>
            测试时间：{result.timestamp}
          </div>
        </>
      )}
    </div>
  );
}
