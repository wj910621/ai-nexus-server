# 商业化功能部署指南

ComicStudio AI Phase 6 商业化功能模块部署与配置说明。

## 功能概览

Phase 6 新增以下商业化能力：

| 模块 | 说明 | 桌面模式行为 |
|------|------|--------------|
| 积分计费 | AI 操作扣减积分，记录交易流水 | 正常工作（本地积分） |
| 订阅计划 | free / pro / enterprise 三档套餐 | 仅 free 可用 |
| 限流 | 按计划分级限流（30/120/600 RPM） | 自动 bypass |
| 邮箱认证 | 注册邮箱验证码 + 密码重置 | 静默跳过（no-op） |
| 管理员 | 用户管理 / 统计 / 封禁 / 积分授予 | 可用 |
| 支付与积分 | 亿界贾维斯主站统一账本 | 不部署独立收款 |
| 审计日志 | 记录敏感操作 | 本地 SQLite 记录 |

## 订阅计划

| 计划 | 价格 | 月积分 | 限流 |
|------|------|--------|------|
| free | 免费 | 100 | 30 RPM |
| pro | ¥49/月 | 2000 | 120 RPM |
| enterprise | ¥299/月 | 20000 | 600 RPM |

## AI 操作积分消耗

| 操作 | 积分 |
|------|------|
| text2img | 10 |
| tts | 5 |
| chat | 1 |
| video_compose | 50 |
| character_generate | 30 |

管理员用户（`role == "admin"`）免除所有积分扣减。

## 环境变量配置

### 邮件（SMTP）
```env
CS_SMTP_HOST=smtp.example.com
CS_SMTP_PORT=587
CS_SMTP_USERNAME=your_username
CS_SMTP_PASSWORD=your_password
CS_SMTP_FROM=no-reply@example.com
CS_SMTP_USE_TLS=true
```
未配置时邮件相关操作静默 no-op，不影响注册流程。

### 支付与积分（亿界贾维斯统一）
```env
BILLING_MODE=jarvis
JARVIS_BILLING_PORTAL_URL=https://ynexai.cn/
JARVIS_GATEWAY_ENABLED=true
JARVIS_GATEWAY_BASE_URL=https://ynexai.cn
JARVIS_GATEWAY_SERVICE_TOKEN=主站签发的计费服务凭据
JARVIS_GATEWAY_DEFAULT_MODEL=已核价模型ID
```
未配置时自动使用 `MockPaymentProvider`。

### 限流（Redis）
```env
CS_RATE_LIMIT_ENABLED=true
RATE_LIMIT_REDIS_URL=redis://redis.internal:6379/1
```
未配置或桌面模式自动 bypass。

### 管理员引导
```env
CS_ADMIN_BOOTSTRAP_EMAIL=admin@example.com
```
首次启动时若该邮箱的用户存在，自动赋予 admin 角色。

## 部署步骤

1. 配置亿界贾维斯主站网关和统一账本凭据
2. 配置环境变量（生产环境）
3. 启动后端：`python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
4. 验证主站积分预授权、实际扣费、失败返还和幂等对账
5. 创建首个管理员：注册用户后通过 `CS_ADMIN_BOOTSTRAP_EMAIL` 或数据库手动设置 `role='admin'`

## 桌面模式（CS_DESKTOP_MODE=1）

所有商业化功能在桌面模式下均有降级方案：
- 邮件：no-op，验证码不发送
- 支付：Mock 模式，模拟支付成功
- 限流：bypass
- 积分/订阅/审计：正常工作（本地 SQLite）

桌面用户可零成本体验所有 AI 功能（免费 100 积分/月）。
