import { Alert, Button, Card, Typography } from 'antd'
import { ExportOutlined, SafetyCertificateOutlined } from '@ant-design/icons'

const portalUrl = import.meta.env.VITE_JARVIS_BILLING_PORTAL_URL || 'https://ynexai.cn/'

export default function BillingPage() {
  const openPortal = () => {
    window.open(portalUrl, '_blank', 'noopener,noreferrer')
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <Typography.Title level={2} className="!text-white">
        统一账户与积分
      </Typography.Title>

      <Card>
        <div className="flex items-start gap-4">
          <SafetyCertificateOutlined className="text-3xl text-blue-500" />
          <div>
            <Typography.Title level={4}>由 Y·NEX 主站统一管理</Typography.Title>
            <Typography.Paragraph>
              Y·NEX 漫剧工坊不单独售卖会员或积分，也不会再次扣除一套本地积分。
              充值、套餐、余额、消费记录、发票及法定例外售后均以主站账户中心为准。
            </Typography.Paragraph>
            <Alert
              type="info"
              showIcon
              className="!mb-5"
              message="一个账户，一套权益，一份账单"
              description="在主站完成充值或套餐变更后，返回漫剧工坊即可继续使用。无需在两个入口重复购买。"
            />
            <Button type="primary" size="large" icon={<ExportOutlined />} onClick={openPortal}>
              前往 Y·NEX 账户中心
            </Button>
          </div>
        </div>
      </Card>

      <Card className="!mt-5" title="计费说明">
        <ul className="list-disc pl-5 space-y-2">
          <li>模型价格、积分扣除和失败返还均由主站统一账本处理。</li>
          <li>漫剧工坊不保存独立支付卡信息，也不配置独立 Stripe 商户。</li>
          <li>数字化服务原则上不支持无理由退款；法定例外由主站订单售后流程处理。</li>
          <li>若主站权益同步失败，漫剧工坊将停止相关收费能力，避免免费使用或重复扣费。</li>
        </ul>
      </Card>
    </div>
  )
}
