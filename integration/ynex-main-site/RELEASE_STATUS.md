# 剩余发布状态

## 代码已完成

- 主站已有 `server_files/story_bridge.js`，并已在 `server.js` 挂载。
- Story Studio 已验证主站签发的 `iss=ynexai.cn`、
  `aud=story-studio` 短期会话。
- HTTP 与 WebSocket 均将 Y·NEX subject 映射到同一个本地项目资料 UUID，
  实时任务频道不会继续使用旧的本地 JWT 身份。
- Story Studio 本地注册、登录和支付在共享模式下关闭。
- 图像、TTS、视频和角色生成通过主站幂等账本先扣费、失败退款。
- 聊天由 Y·NEX OpenAI 兼容网关计费，避免再次调用固定操作扣费造成双扣。
- 主站令牌仅用于换票，Story API 不接受主站原始令牌。

## 部署时必须提供

主站：

```text
STORY_SSO_SECRET=<至少32字符>
STORY_SERVICE_TOKEN=<至少32字符>
STORY_CREDIT_PRICING_JSON=<经70%利润门禁审核的操作价格JSON>
```

Story Studio：

```text
BILLING_MODE=jarvis
YNEX_SSO_SECRET=<与主站 STORY_SSO_SECRET 相同>
YNEX_SSO_ISSUER=ynexai.cn
YNEX_SSO_AUDIENCE=story-studio
YNEX_BILLING_BASE_URL=https://ynexai.cn
YNEX_BILLING_SERVICE_TOKEN=<与主站 STORY_SERVICE_TOKEN 相同>
```

密钥只能通过服务器密钥管理或受限环境文件注入，不得写入仓库。

## 尚需生产环境验证

- 主站与 Story Studio 环境变量已注入且非占位值。
- 数据库迁移 `013_add_ynex_subject` 成功。
- Story API、Worker、PostgreSQL、Redis 和对象存储健康。
- 真实账户完成换票、扣费、余额不足、生成失败退款和重复请求幂等测试。
- `nginx -t` 通过后才能应用 `ynex-main-site.patch` 并开放入口。

运行 `deploy/preflight-story-production.ps1`；只有返回
`Story production preflight passed` 才允许重载 Nginx。
