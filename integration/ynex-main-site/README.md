# Y·NEX 主站接入包

统一品牌：

- 母品牌：`Y·NEX`
- 英文产品名：`Y·NEX Story Studio`
- 中文产品名：`Y·NEX 漫剧工坊`
- 欢迎页简称：`漫剧工坊`

## 同域路由

| 路径 | 所属服务 | 用途 |
| --- | --- | --- |
| `/` | Y·NEX 主站 | 欢迎页、账户、会员、积分、订单与售后 |
| `/story/` | Story Studio 前端 | 在线漫剧创作 |
| `/story-api/` | Story Studio 后端 | 漫剧业务 API |
| `/story-ws/` | Story Studio 后端 | 实时任务状态 |
| `/download/story/` | Y·NEX 下载中心 | Story Studio 桌面版下载 |

同一服务器和域名不等于合并进程。主站、Story Studio 后端、任务队列和
模型工作进程应作为独立服务运行，由同一个 HTTPS 入口反向代理。这样可以
共享用户体验，同时隔离故障和资源峰值。

## 主站改动

1. 将 `welcome-card.html` 合入欢迎页产品网格，并按主站设计系统调整
   `welcome-card.css`。
2. 将 `nginx-ynex-story.conf` 中的 location 合入现有
   `ynexai.cn` HTTPS server block。
3. Story Studio Web 构建使用：

   ```text
   VITE_BASE_PATH=/story/
   VITE_ROUTER_BASE=/story
   VITE_API_BASE_URL=/story-api
   VITE_WS_BASE_URL=/story-ws
   VITE_JARVIS_BILLING_PORTAL_URL=/
   ```

4. 将 Web 构建产物部署到 `/srv/ynex/story-web/`。
5. 下载页部署到 `/srv/ynex/story-downloads/index.html`；安装包只通过
   该下载页公开，不在欢迎页写死版本号。

## 账户和积分边界

- Y·NEX 主站是账户、会员、积分、订单、发票和售后的唯一数据源。
- Story Studio 不配置第二套支付、充值、积分余额或退款入口。
- 当前登录页仅从同源 `auth_token` 读取主站现有登录态，并通过
  `POST /api/story/session` 换取短期漫剧会话；不复制主站令牌到其他键，
  漫剧服务只接受并校验 `aud=story-studio` 的换票结果。主站完成
  HttpOnly Cookie 迁移后再移除该兼容读取。
- Story Studio 服务端通过受控的服务间接口查询权益并提交幂等计量记录。
- 计量失败时停止收费任务，避免漏扣或重复扣费。

## 上线门槛

- `/story/` 的所有静态资源和前端路由可在子路径刷新。
- `/story-api/` 与 `/story-ws/` 只经 HTTPS/WSS 暴露。
- 主站登录、退出、积分扣减、失败回滚和订单售后各完成一次端到端验证。
- 下载页展示版本、平台、文件大小、SHA-256 和发布状态；未验证的安装包
  不得公开。
