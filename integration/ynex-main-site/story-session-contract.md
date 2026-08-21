# `POST /api/story/session` 契约

该接口由 Y·NEX 主站实现，是主站登录态进入漫剧工坊的唯一浏览器换票入口。

## 请求

- 必须是 HTTPS 同源请求。
- 当前主站通过 `Authorization: Bearer <auth_token>` 验证登录态；漫剧前端
  只使用它完成一次换票，不复制或长期保存主站令牌。
- 必须校验 `Origin`/`Sec-Fetch-Site`，并建议要求
  `X-Requested-With: Y-NEX-Story-Studio`。
- 不接受通过请求体或查询参数提交主站 JWT。
- 主站迁移到 `HttpOnly; Secure; SameSite` Cookie 后，换票接口应同步移除
  浏览器读取 `localStorage` 的兼容逻辑。

## 成功响应

```json
{
  "token": "<short-lived-story-access-token>",
  "expires_in": 900
}
```

短期令牌至少包含：

- `iss`：Y·NEX 主站认证服务
- `sub`：稳定且不可复用的用户标识
- `aud`：`story-studio`
- `exp`、`iat`、`jti`
- 当前会员或权限版本号；积分余额仍以服务端账本实时查询为准

## 错误响应

- `401`：主站未登录或会话过期
- `403`：来源、CSRF 或产品权限校验失败
- `429`：换票过于频繁
- `503`：认证或权益服务暂时不可用

接口不得在日志中记录 Cookie、主站令牌或签发后的完整访问令牌。
